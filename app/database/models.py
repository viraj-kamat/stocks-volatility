from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class PinnedStock(Base):
    """User-pinned symbols for the dashboard watchlist (shared across sessions/devices)."""

    __tablename__ = "pinned_stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    pin_order = Column(Integer, nullable=False, default=0)
    pinned_at = Column(DateTime, default=datetime.utcnow)
