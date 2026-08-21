from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.database.connection import get_db
from app.database.models import Alert, Stock
from app.config import app_config
from app.scheduler.jobs import run_analysis_job, cleanup_old_alerts
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/stocks")
def get_stocks(db: Session = Depends(get_db)):
    """Get all monitored stocks with latest price and volatility status."""
    try:
        stocks = db.query(Stock).all()

        # Get latest alerts count for each stock
        result = []
        for stock in stocks:
            alert_count = db.query(Alert).filter(
                Alert.symbol == stock.symbol,
                Alert.is_read == False
            ).count()

            result.append({
                "symbol": stock.symbol,
                "price": stock.last_price,
                "last_update": stock.last_update.isoformat() if stock.last_update else None,
                "unread_alerts": alert_count,
            })

        return result
    except Exception as e:
        logger.error(f"Error getting stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
def get_alerts(db: Session = Depends(get_db), limit: int = 50, skip: int = 0):
    """Get recent alerts."""
    try:
        alerts = db.query(Alert).order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()

        return [
            {
                "id": alert.id,
                "symbol": alert.symbol,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "triggered_at": alert.triggered_at.isoformat(),
                "price_at_trigger": alert.price_at_trigger,
                "percent_change": alert.percent_change,
                "is_read": alert.is_read,
                "created_at": alert.created_at.isoformat(),
            }
            for alert in alerts
        ]
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
