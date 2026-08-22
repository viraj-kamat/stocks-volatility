from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from app.database.connection import get_db
from app.database.models import Alert, Stock
from app.config import app_config
from app.scheduler.jobs import run_analysis_job, cleanup_old_alerts
from app.data.fetcher import StockDataFetcher
from app.data.cache import cache
from app.utils.datetime_fmt import format_date_short, format_datetime_display
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

SEVERITY_TO_COLOR = {"high": "red", "medium": "yellow", "low": "blue"}


def _latest_alert_info(db: Session, symbol: str) -> dict:
    """Latest stored alert: severity color + short date for the Last Alert column."""
    latest = (
        db.query(Alert)
        .filter(Alert.symbol == symbol)
        .order_by(Alert.triggered_at.desc(), Alert.id.desc())
        .first()
    )
    if not latest:
        return {
            "color": "green",
            "severity": None,
            "alert_type": None,
            "triggered_at_display": None,
        }

    return {
        "color": SEVERITY_TO_COLOR.get(latest.severity, "blue"),
        "severity": latest.severity,
        "alert_type": latest.alert_type,
        "triggered_at_display": format_date_short(latest.triggered_at, app_config.timezone),
    }


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
    """Fetch realtime quotes, with a short Redis cache to limit Yahoo calls."""
    cached = cache.get_cached_latest_prices()
    if cached and all(s in cached for s in symbols):
        return cached

    fetcher = StockDataFetcher()
    quotes = {}
    for i, symbol in enumerate(symbols):
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

        result = []
        for symbol in symbols:
            quote = quotes.get(symbol) or {}
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            alert_count = db.query(Alert).filter(
                Alert.symbol == symbol,
                Alert.is_read == False,
            ).count()

            latest_alert = _latest_alert_info(db, symbol)
            live = _live_move_color(quote.get("percent_change"), threshold)

            result.append({
                "symbol": symbol,
                "name": stock.name if stock else None,
                "current_price": quote.get("current_price"),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "previous_close": quote.get("previous_close"),
                "volume": quote.get("volume"),
                "change": quote.get("change"),
                "percent_change": quote.get("percent_change"),
                "as_of": quote.get("as_of"),
                "alert": latest_alert["color"],
                "alert_severity": latest_alert["severity"],
                "alert_date": latest_alert["triggered_at_display"],
                "live": live["color"],
                "live_label": live["label"],
                "unread_alerts": alert_count,
                "last_update": stock.last_update.isoformat() if stock and stock.last_update else None,
                # backward-compatible field
                "price": quote.get("current_price") or (stock.last_price if stock else None),
            })

        return result
    except Exception as e:
        logger.error(f"Error getting stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _format_alert_message(alert: Alert, tz_name: str) -> str:
    """Rebuild display message so older DB rows pick up the new date format."""
    on_date = format_date_short(alert.triggered_at, tz_name)
    if alert.alert_type == "pattern":
        return f"{alert.symbol} bounced sharply after sustained decline on {on_date}"
    if alert.percent_change is None:
        return f"{alert.symbol} alert on {on_date}"
    return f"{alert.symbol} moved {alert.percent_change:.2f}% on {on_date}"


@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=100),
    skip: int = Query(0, ge=0),
    symbol: Optional[str] = Query(None, description="Filter alerts by stock symbol"),
):
    """Get recent alerts, optionally filtered by symbol (paginated)."""
    try:
        tz_name = app_config.timezone
        query = db.query(Alert)
        if symbol:
            query = query.filter(Alert.symbol == symbol.upper())

        total = query.count()
        alerts = query.order_by(Alert.triggered_at.desc()).offset(skip).limit(limit).all()

        return {
            "items": [
                {
                    "id": alert.id,
                    "symbol": alert.symbol,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "message": _format_alert_message(alert, tz_name),
                    "triggered_at": alert.triggered_at.isoformat(),
                    "triggered_at_display": format_datetime_display(alert.triggered_at, tz_name),
                    "price_at_trigger": alert.price_at_trigger,
                    "percent_change": alert.percent_change,
                    "is_read": alert.is_read,
                    "created_at": alert.created_at.isoformat(),
                    "timezone": tz_name,
                }
                for alert in alerts
            ],
            "total": total,
            "limit": limit,
            "skip": skip,
            "timezone": tz_name,
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
def trigger_refresh(db: Session = Depends(get_db)):
    """Manually trigger analysis job."""
    try:
        logger.info("Manual refresh triggered")
        result = run_analysis_job()

        # Also cleanup old alerts
        cleanup_old_alerts(db)

        return result
    except Exception as e:
        logger.error(f"Error in manual refresh: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
def get_config():
    """Get current configuration."""
    return {
        "symbols": app_config.symbols,
        "volatility_threshold": app_config.volatility_threshold,
        "lookback_days": app_config.lookback_days,
        "scheduler_interval_hours": app_config.scheduler_interval_hours,
        "timezone": app_config.timezone,
    }


@router.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    """Mark an alert as read."""
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert.is_read = True
        db.commit()

        return {"id": alert.id, "is_read": alert.is_read}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking alert as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
