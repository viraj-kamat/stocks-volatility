import yfinance as yf
import logging
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

            # Fetch data from yfinance
            data = yf.download(symbol, start=start_date, end=end_date, progress=False)

            if data.empty:
                logger.warning(f"No data fetched for {symbol}")
                return None

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
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1d")

            if hist.empty:
                return None

            latest = hist.iloc[-1]
            return {
                "symbol": symbol,
                "price": float(latest['Close']),
                "change": float(latest['Close'] - hist.iloc[-2]['Close']) if len(hist) > 1 else 0,
                "percent_change": float((latest['Close'] / hist.iloc[-2]['Close'] - 1) * 100) if len(hist) > 1 else 0,
                "timestamp": hist.index[-1],
            }
        except Exception as e:
            logger.error(f"Error fetching latest price for {symbol}: {e}")
            return None

    def fetch_multiple(self, symbols: List[str]) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch data for multiple symbols.
        """
        results = {}
        for symbol in symbols:
            results[symbol] = self.fetch_historical_data(symbol)
        return results
