"""Alpaca Market Data snapshots for live quotes."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from app.config import settings

logger = logging.getLogger(__name__)

ALPACA_DATA_URL = "https://data.alpaca.markets/v2/stocks/snapshots"


def alpaca_configured() -> bool:
    return bool(settings.alpaca_api_key and settings.alpaca_api_secret)


def _preferred_feed() -> str:
    """
    Use overnight feed outside regular US cash hours when enabled;
    otherwise the configured feed (default iex — free tier).
    """
    configured = (settings.alpaca_data_feed or "iex").strip().lower()
    if configured != "auto":
        return configured

    now = datetime.now(ZoneInfo("America/New_York"))
    # Alpaca overnight session ~ 8pm–4am ET
    if now.hour >= 20 or now.hour < 4:
        return "overnight"
    return "iex"


def _price_from_snapshot(snap: dict) -> Optional[float]:
    trade = snap.get("latestTrade") or {}
    if trade.get("p") is not None:
        return float(trade["p"])

    quote = snap.get("latestQuote") or {}
    bid, ask = quote.get("bp"), quote.get("ap")
    if bid and ask and float(bid) > 0 and float(ask) > 0:
        return (float(bid) + float(ask)) / 2.0
    if ask and float(ask) > 0:
        return float(ask)
    if bid and float(bid) > 0:
        return float(bid)

    daily = snap.get("dailyBar") or {}
    if daily.get("c") is not None:
        return float(daily["c"])
    return None


def _snapshot_to_quote(symbol: str, snap: dict) -> Optional[Dict]:
    current = _price_from_snapshot(snap)
    if current is None:
        return None

    daily = snap.get("dailyBar") or {}
    prev = snap.get("prevDailyBar") or {}
    previous_close = float(prev["c"]) if prev.get("c") is not None else None
    if previous_close is None and daily.get("o") is not None:
        previous_close = float(daily["o"])

    change = None
    percent_change = None
    if previous_close:
        change = current - previous_close
        percent_change = change / previous_close * 100

    trade = snap.get("latestTrade") or {}
    as_of = trade.get("t") or (snap.get("minuteBar") or {}).get("t") or daily.get("t")

    return {
        "symbol": symbol,
        "open": float(daily["o"]) if daily.get("o") is not None else None,
        "high": float(daily["h"]) if daily.get("h") is not None else None,
        "low": float(daily["l"]) if daily.get("l") is not None else None,
        "current_price": float(current),
        "previous_close": float(previous_close) if previous_close is not None else None,
        "volume": int(daily["v"]) if daily.get("v") is not None else None,
        "change": float(change) if change is not None else None,
        "percent_change": float(percent_change) if percent_change is not None else None,
        "as_of": as_of,
        "source": "alpaca",
    }


def fetch_snapshots(symbols: List[str], feed: Optional[str] = None) -> Dict[str, Dict]:
    """
    Batch-fetch Alpaca snapshots. Returns symbol → quote dict (StockSpikes shape).
    """
    if not symbols or not alpaca_configured():
        return {}

    feed = feed or _preferred_feed()
    quotes = _request_snapshots(symbols, feed)

    # Overnight can 403 on some plans — retry with iex
    if not quotes and feed == "overnight":
        logger.warning("Alpaca overnight feed returned nothing; retrying with iex")
        quotes = _request_snapshots(symbols, "iex")

    return quotes


def _request_snapshots(symbols: List[str], feed: str) -> Dict[str, Dict]:
    params = urllib.parse.urlencode({
        "symbols": ",".join(symbols),
        "feed": feed,
    })
    url = f"{ALPACA_DATA_URL}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "APCA-API-KEY-ID": settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.error("Alpaca snapshot HTTP %s feed=%s: %s", e.code, feed, body[:300])
        return {}
    except Exception as e:
        logger.error("Alpaca snapshot request failed: %s", e)
        return {}

    quotes: Dict[str, Dict] = {}
    if not isinstance(payload, dict):
        return {}

    for symbol in symbols:
        snap = payload.get(symbol) or payload.get(symbol.upper())
        if not snap:
            continue
        quote = _snapshot_to_quote(symbol.upper(), snap)
        if quote:
            quotes[symbol.upper()] = quote

    logger.info("Alpaca snapshots feed=%s symbols=%s hit=%s", feed, len(symbols), len(quotes))
    return quotes
