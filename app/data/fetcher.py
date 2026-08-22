import yfinance as yf
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class StockDataFetcher:
    def __init__(self, lookback_days: int = 365):
        self.lookback_days = lookback_days

    def fetch_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical stock data for the given symbol.
        Returns a DataFrame with OHLCV data and calculated percent changes.
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_days)

            logger.info(f"Fetching data for {symbol} from {start_date.date()} to {end_date.date()}")

            # Prefer Ticker.history; more reliable against Yahoo rate/API quirks
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, auto_adjust=True)

            if data.empty:
                logger.warning(f"No data fetched for {symbol}")
                return None

            # Flatten multi-index columns if present (newer yfinance)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Calculate daily percent change
            data['Percent_Change'] = data['Close'].pct_change() * 100

            # Reset index to make Date a column
            data.reset_index(inplace=True)

            logger.info(f"Successfully fetched {len(data)} rows for {symbol}")
            return data

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

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

            current = float(latest["Close"])
            previous_close = float(prev["Close"])
            change = current - previous_close
            percent_change = (change / previous_close * 100) if previous_close else 0.0

            as_of = latest.name
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
            }
        except Exception as e:
            logger.error(f"Error fetching realtime quote for {symbol}: {e}")
            return None

    def fetch_multiple(self, symbols: List[str]) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch data for multiple symbols.
        """
        results = {}
        for i, symbol in enumerate(symbols):
            if i > 0:
                time.sleep(1)  # avoid Yahoo rate limits
            results[symbol] = self.fetch_historical_data(symbol)
        return results
