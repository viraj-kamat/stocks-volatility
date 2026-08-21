import pandas as pd
import logging
from typing import List, Dict, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class VolatilityAnalyzer:
    def __init__(self, threshold: float = 5.0):
        self.threshold = threshold

    def detect_sharp_moves(self, data: pd.DataFrame, symbol: str) -> List[Dict]:
        """
        Detect sharp up and down moves in stock price data.
        Returns a list of alert dictionaries.
        """
        alerts = []

        if data is None or data.empty:
            logger.warning(f"No data available for {symbol}")
            return alerts

        # Ensure we have percent change calculated
        if 'Percent_Change' not in data.columns:
            data['Percent_Change'] = data['Close'].pct_change() * 100

        # Find sharp moves
        for idx, row in data.iterrows():
            if pd.isna(row['Percent_Change']):
                continue

            abs_change = abs(row['Percent_Change'])
            if abs_change >= self.threshold:
                alert_type = "sharp_up" if row['Percent_Change'] > 0 else "sharp_down"
                severity = self._calculate_severity(abs_change)

                alert = {
                    "symbol": symbol,
                    "alert_type": alert_type,
                    "severity": severity,
                    "message": f"{symbol} moved {row['Percent_Change']:.2f}% on {row['Date'].strftime('%Y-%m-%d')}",
                    "triggered_at": row['Date'],
                    "price_at_trigger": float(row['Close']),
                    "percent_change": float(row['Percent_Change']),
                }
                alerts.append(alert)

        logger.info(f"Found {len(alerts)} sharp moves for {symbol}")
        return alerts

    def detect_volatility_patterns(self, data: pd.DataFrame, symbol: str) -> List[Dict]:
        """
        Detect volatility patterns like downs followed by sharp ups.
        """
        alerts = []

        if data is None or data.empty:
            logger.warning(f"No data available for {symbol}")
            return alerts

        if 'Percent_Change' not in data.columns:
            data['Percent_Change'] = data['Close'].pct_change() * 100

        # Create a sequence of ups/downs
        data['Direction'] = data['Percent_Change'].apply(lambda x: 'up' if x > 0 else 'down' if x < 0 else 'flat')

        # Find patterns: down, down/flat, sharp up
        for idx in range(2, len(data)):
            curr = data.iloc[idx]
            prev1 = data.iloc[idx - 1]
            prev2 = data.iloc[idx - 2]

            # Pattern: down, down, sharp up
            if (prev2['Direction'] == 'down' and prev1['Direction'] == 'down' and
                    curr['Direction'] == 'up' and abs(curr['Percent_Change']) >= self.threshold):

                alert = {
                    "symbol": symbol,
                    "alert_type": "pattern",
                    "severity": "high",
                    "message": f"{symbol} bounced sharply after sustained decline on {curr['Date'].strftime('%Y-%m-%d')}",
                    "triggered_at": curr['Date'],
                    "price_at_trigger": float(curr['Close']),
                    "percent_change": float(curr['Percent_Change']),
                }
                alerts.append(alert)

        logger.info(f"Found {len(alerts)} volatility patterns for {symbol}")
        return alerts

    def _calculate_severity(self, percent_change: float) -> str:
        """Calculate severity based on magnitude of change."""
        abs_change = abs(percent_change)
        if abs_change >= 15:
            return "high"
        elif abs_change >= 10:
            return "medium"
        else:
            return "low"

    def analyze_volatility(self, data: pd.DataFrame, symbol: str) -> Dict:
        """
        Comprehensive volatility analysis.
        """
        if data is None or data.empty:
            return {
                "symbol": symbol,
                "avg_volatility": 0,
                "max_move": 0,
                "sharp_moves_count": 0,
                "patterns_count": 0,
            }

        if 'Percent_Change' not in data.columns:
            data['Percent_Change'] = data['Close'].pct_change() * 100

        # Remove NaN values for statistics
        changes = data['Percent_Change'].dropna()

        return {
            "symbol": symbol,
            "avg_volatility": float(changes.std()),
            "max_move": float(changes.max()),
            "min_move": float(changes.min()),
            "sharp_moves_count": int((abs(changes) >= self.threshold).sum()),
            "high_volatility_days": int((abs(changes) >= 10).sum()),
            "data_points": len(data),
        }
