import yfinance as yf
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StockDataFetcher:
    def __init__(self, lookback_days: int = 365):
        self.lookback_days = lookback_days

    def fetch_company_name(self, symbol: str) -> Optional[str]:
        """Company display name from Yahoo (None if unavailable)."""
        try:
            info = yf.Ticker(symbol).get_info()
            return info.get("longName") or info.get("shortName")
        except Exception as e:
            logger.error(f"Error fetching company name for {symbol}: {e}")
            return None
