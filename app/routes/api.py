from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel
from app.database.connection import get_db
from app.data.session import current_session
from app.database.models import PinnedStock
from app.config import app_config
from app.data.fetcher import StockDataFetcher
from app.data.cache import cache
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

SEVERITY_TO_COLOR = {"high": "red", "medium": "yellow", "low": "blue"}


class PinRequest(BaseModel):
    pinned: bool


def _pinned_map(db: Session) -> dict:
    """symbol → pin_order for all pinned stocks."""
    rows = (
        db.query(PinnedStock)
        .order_by(PinnedStock.pin_order.asc(), PinnedStock.id.asc())
        .all()
    )
    return {row.symbol.upper(): row.pin_order for row in rows}


def _severity_for_move(percent_change: float, threshold: float) -> str:
    """Same bands as VolatilityAnalyzer: low < T, medium < 3T, high >= 3T."""
    abs_pct = abs(float(percent_change))
    if abs_pct >= 3 * threshold:
        return "high"
    if abs_pct >= threshold:
        return "medium"
    return "low"


def _live_move_color(percent_change: Optional[float], threshold: float) -> dict:
    """Live column uses the same severity→color mapping as Alert history."""
    if percent_change is None:
        return {"color": "green", "label": "n/a", "severity": None}

    severity = _severity_for_move(percent_change, threshold)
    return {
        "color": SEVERITY_TO_COLOR.get(severity, "blue"),
        "label": severity,
        "severity": severity,
    }


def _get_realtime_quotes(symbols: list) -> dict:
    """Fetch realtime quotes (Alpaca preferred), with Redis cache."""
    cached = cache.get_cached_latest_prices()
    if cached and all(s in cached for s in symbols):
        return cached

    quotes = {}
    from app.data.alpaca import alpaca_configured, fetch_snapshots

    if alpaca_configured():
        raw = fetch_snapshots(symbols)
        for symbol in symbols:
            quote = raw.get(symbol) or raw.get(symbol.upper())
            if quote:
                quotes[symbol] = quote
    else:
        logger.warning("ALPACA_API_KEY/SECRET not set — live quotes fall back to Yahoo")

    # Fill any missing symbols via Yahoo
    missing = [s for s in symbols if s not in quotes]
    if missing:
        fetcher = StockDataFetcher()
        for i, symbol in enumerate(missing):
            if i > 0:
                time.sleep(0.4)
            quote = fetcher.fetch_realtime_quote(symbol)
            if quote:
                quotes[symbol] = quote

    if quotes:
        cache.cache_latest_prices(quotes, ttl_minutes=1)
    return quotes


@router.get("/stocks")
def get_stocks(db: Session = Depends(get_db)):
    """Get monitored stocks with realtime quotes, latest alert, and live move colors."""
    try:
        symbols = app_config.symbols
        threshold = app_config.volatility_threshold
        quotes = _get_realtime_quotes(symbols)
        pinned = _pinned_map(db)

        result = []
        for symbol in symbols:
            quote = quotes.get(symbol) or {}
            live = _live_move_color(quote.get("percent_change"), threshold)
            sym_upper = symbol.upper()
            is_pinned = sym_upper in pinned

            result.append({
                "symbol": symbol,
                "current_price": quote.get("current_price"),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "previous_close": quote.get("previous_close"),
                "volume": quote.get("volume"),
                "change": quote.get("change"),
                "percent_change": quote.get("percent_change"),
                "as_of": quote.get("as_of"),
                "market_session": current_session(),
                "source": quote.get("source"),
                "live": live["color"],
                "live_label": live["label"],
                "pinned": is_pinned,
                "pin_order": pinned.get(sym_upper) if is_pinned else None,
                "price": quote.get("current_price"),
            })

        return result
    except Exception as e:
        logger.error(f"Error getting stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/stocks/{symbol}/pin")
def set_stock_pin(symbol: str, body: PinRequest, db: Session = Depends(get_db)):
    """Pin or unpin a watchlist symbol (persisted in MySQL)."""
    sym = symbol.upper().strip()
    watchlist = {s.upper() for s in app_config.symbols}
    if sym not in watchlist:
        raise HTTPException(status_code=404, detail=f"{sym} is not on the watchlist")

    existing = db.query(PinnedStock).filter(PinnedStock.symbol == sym).first()

    if body.pinned:
        if existing:
            return {"symbol": sym, "pinned": True, "pin_order": existing.pin_order}
        max_order = db.query(func.max(PinnedStock.pin_order)).scalar()
        next_order = (max_order if max_order is not None else -1) + 1
        db.add(PinnedStock(symbol=sym, pin_order=next_order))
        db.commit()
        return {"symbol": sym, "pinned": True, "pin_order": next_order}

    if existing:
        db.delete(existing)
        db.commit()
    return {"symbol": sym, "pinned": False, "pin_order": None}


@router.get("/config")
def get_config():
    """Get current configuration."""
    return {
        "symbols": app_config.symbols,
        "volatility_threshold": app_config.volatility_threshold,
        "timezone": app_config.timezone,
    }


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
