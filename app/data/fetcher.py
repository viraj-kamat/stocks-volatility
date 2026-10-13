import yfinance as yf
import logging
import pandas as pd
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class StockDataFetcher:
    def __init__(self, lookback_days: int = 365):
        self.lookback_days = lookback_days

    def fetch_latest_price(self, symbol: str) -> Optional[Dict]:
        """
        Fetch the latest price data for a symbol.
        """
        quote = self.fetch_realtime_quote(symbol)
        if not quote:
            return None
        return {
            "symbol": quote["symbol"],
            "price": quote["current_price"],
            "change": quote["change"],
            "percent_change": quote["percent_change"],
            "timestamp": quote["as_of"],
        }

    def fetch_realtime_quote(self, symbol: str) -> Optional[Dict]:
        """
        Fetch near-realtime OHLC quote for a symbol (latest session).
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d", auto_adjust=True)

            if hist.empty:
                logger.warning(f"No realtime quote for {symbol}")
                return None

            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = hist.columns.get_level_values(0)

            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest

            as_of_ext = None
            current = float(latest["Close"])
            # Extended hours (pre/post): latest 1m bar incl. pre/post market
            try:
                ext = ticker.history(period="1d", interval="1m", prepost=True, auto_adjust=True)
                if not ext.empty:
                    if isinstance(ext.columns, pd.MultiIndex):
                        ext.columns = ext.columns.get_level_values(0)
                    current = float(ext.iloc[-1]["Close"])
                    as_of_ext = ext.index[-1]
            except Exception as ext_err:
                logger.debug(f"No extended-hours data for {symbol}: {ext_err}")
                as_of_ext = None
            previous_close = float(prev["Close"])
            change = current - previous_close
            percent_change = (change / previous_close * 100) if previous_close else 0.0

            as_of = as_of_ext if as_of_ext is not None else latest.name
            if hasattr(as_of, "isoformat"):
                as_of = as_of.isoformat()
            else:
                as_of = str(as_of)

            return {
                "symbol": symbol,
                "open": float(latest["Open"]),
                "high": float(latest["High"]),
                "low": float(latest["Low"]),
                "current_price": current,
                "previous_close": previous_close,
                "volume": int(latest["Volume"]) if pd.notna(latest["Volume"]) else None,
                "change": float(change),
                "percent_change": float(percent_change),
                "as_of": as_of,
                "source": "yahoo",
            }
        except Exception as e:
            logger.error(f"Error fetching realtime quote for {symbol}: {e}")
            return None

    def fetch_company_name(self, symbol: str) -> Optional[str]:
        """Company display name from Yahoo (None if unavailable)."""
        try:
            info = yf.Ticker(symbol).get_info()
            return info.get("longName") or info.get("shortName")
        except Exception as e:
            logger.error(f"Error fetching company name for {symbol}: {e}")
            return None
