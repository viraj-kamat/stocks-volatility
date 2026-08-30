from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    last_price = Column(Float, nullable=True)
    last_update = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Per-symbol watermark: first/new symbols get full lookback; later runs only newer days
    last_analyzed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # "sharp_up", "sharp_down", "pattern"
    severity = Column(String(20), default="medium")  # "low", "medium", "high"
    message = Column(Text, nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    price_at_trigger = Column(Float, nullable=True)
    percent_change = Column(Float, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True)
    run_at = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(20), default="completed")  # "running", "completed", "failed"
    error_message = Column(Text, nullable=True)
    symbols_processed = Column(Integer, default=0)
    alerts_generated = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PriceData(Base):
    __tablename__ = "price_data"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), nullable=False, index=True)
    date = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=True)
    percent_change = Column(Float, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Unique constraint to prevent duplicates
        # Note: SQLAlchemy doesn't support unique composite easily in declarative
        # We'll handle this in connection.py with raw SQL
    )


class PinnedStock(Base):
    """User-pinned symbols for the dashboard watchlist (shared across sessions/devices)."""

    __tablename__ = "pinned_stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    pin_order = Column(Integer, nullable=False, default=0)
    pinned_at = Column(DateTime, default=datetime.utcnow)
