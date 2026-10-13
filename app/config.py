import os
from typing import List
import yaml
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mysql_host: str = os.getenv("MYSQL_HOST", "localhost")
    mysql_user: str = os.getenv("MYSQL_USER", "stocks_user")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "stocks_password")
    mysql_database: str = os.getenv("MYSQL_DATABASE", "stocks_db")
    mysql_port: int = int(os.getenv("MYSQL_PORT", 3306))

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))

    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Dashboard password (from STOCKSPIKES_PWD). Empty disables auth.
    stockspikes_pwd: str = os.getenv("STOCKSPIKES_PWD", "")

    # Alpaca market data (live quotes). Empty → fall back to Yahoo for live.
    alpaca_api_key: str = os.getenv("ALPACA_API_KEY", "")
    alpaca_api_secret: str = os.getenv("ALPACA_API_SECRET", "")
    # iex (free), sip (paid), overnight, or auto (iex daytime / overnight late night)
    alpaca_data_feed: str = os.getenv("ALPACA_DATA_FEED", "auto")

    class Config:
        env_file = ".env"


settings = Settings()


class AppConfig:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self._mtime: float | None = None
        self.config_data = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f) or {}
        try:
            self._mtime = self.config_path.stat().st_mtime
        except OSError:
            self._mtime = None
        return data

    def reload(self):
        """Reload config from file (for hot-reload support)"""
        self.config_data = self._load_config()

    def _ensure_fresh(self) -> None:
        """Pick up config.yaml edits without restarting the process."""
        try:
            mtime = self.config_path.stat().st_mtime
        except OSError:
            return
        if self._mtime is None or mtime != self._mtime:
            self.reload()

    @property
    def symbols(self) -> List[str]:
        self._ensure_fresh()
        return self.config_data.get("symbols", [])

    @property
    def volatility_threshold(self) -> float:
        self._ensure_fresh()
        return self.config_data.get("volatility", {}).get("threshold", 5.0)

    @property
    def lookback_days(self) -> int:
        self._ensure_fresh()
        return self.config_data.get("volatility", {}).get("lookback_days", 365)

    @property
    def scheduler_interval_hours(self) -> int:
        self._ensure_fresh()
        return self.config_data.get("scheduler", {}).get("interval_hours", 4)

    @property
    def max_alert_history(self) -> int:
        self._ensure_fresh()
        return self.config_data.get("alerts", {}).get("max_history", 1000)

    @property
    def alert_retention_days(self) -> int:
        self._ensure_fresh()
        return self.config_data.get("alerts", {}).get("retention_days", 90)

    @property
    def timezone(self) -> str:
        self._ensure_fresh()
        return self.config_data.get("timezone", "CT")


app_config = AppConfig()
