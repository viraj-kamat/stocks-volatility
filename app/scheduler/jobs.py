import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.data.fetcher import StockDataFetcher
from app.data.cache import cache
from app.analysis.volatility import VolatilityAnalyzer
from app.database.models import Alert, AnalysisRun, Stock
from app.database.connection import SessionLocal
from app.config import app_config
import time

logger = logging.getLogger(__name__)


def _normalize_ts(value):
    """Normalize pandas/py tz timestamps to naive datetime for comparisons."""
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if getattr(value, "tzinfo", None) is not None:
        value = value.replace(tzinfo=None)
    return value


def _alert_exists(db: Session, symbol: str, alert_type: str, triggered_at) -> bool:
    """True if an alert for this symbol/type/calendar day already exists."""
    ts = _normalize_ts(triggered_at)
    if ts is None:
        return False
    day = ts.date()
    existing = (
        db.query(Alert)
        .filter(
            Alert.symbol == symbol,
            Alert.alert_type == alert_type,
            func.date(Alert.triggered_at) == day,
        )
        .first()
    )
    return existing is not None


def run_analysis_job():
    """
    Main scheduled job to fetch data, run analysis, and generate alerts.

    - New symbols (no last_analyzed_at): full lookback alerts.
    - Existing symbols: only alerts with triggered_at after last_analyzed_at.
    """
    logger.info("=== Starting scheduled analysis job ===")
    start_time = datetime.utcnow()

    db = SessionLocal()
    try:
        # Create analysis run record
        run = AnalysisRun(
            run_at=start_time,
            status="running",
        )
        db.add(run)
        db.commit()

        # Get configuration
        symbols = app_config.symbols
        threshold = app_config.volatility_threshold
        lookback_days = app_config.lookback_days

        logger.info(f"Analyzing {len(symbols)} symbols with threshold {threshold}%")

        # Initialize fetcher and analyzer
        fetcher = StockDataFetcher(lookback_days=lookback_days)
        analyzer = VolatilityAnalyzer(threshold=threshold)

        symbols_processed = 0
        alerts_generated = 0

        for i, symbol in enumerate(symbols):
            try:
                if i > 0:
                    time.sleep(1)  # avoid Yahoo rate limits

                # Fetch data
                data = fetcher.fetch_historical_data(symbol)
                if data is None:
                    logger.warning(f"Failed to fetch data for {symbol}")
                    continue

                # Cache the data
                cache.cache_stock_data(symbol, data)

                # Get or create stock record
                stock = db.query(Stock).filter(Stock.symbol == symbol).first()
                if not stock:
                    stock = Stock(symbol=symbol)
                    db.add(stock)
                    db.flush()

                stock.last_price = float(data['Close'].iloc[-1])
                stock.last_update = datetime.utcnow()

                cutoff = _normalize_ts(stock.last_analyzed_at)
                is_first_run = cutoff is None
                if is_first_run:
                    logger.info(f"{symbol}: first analysis (full lookback)")
                else:
                    logger.info(f"{symbol}: incremental analysis since {cutoff.isoformat()}")

                # Run analysis on full series (patterns need prior days)
                sharp_moves = analyzer.detect_sharp_moves(data, symbol)
                patterns = analyzer.detect_volatility_patterns(data, symbol)
                all_alerts = sharp_moves + patterns

                # Incremental: only keep events after the last successful analysis
                if not is_first_run:
                    all_alerts = [
                        a for a in all_alerts
                        if _normalize_ts(a["triggered_at"]) is not None
                        and _normalize_ts(a["triggered_at"]) > cutoff
                    ]

                new_count = 0
                for alert_data in all_alerts:
                    if _alert_exists(db, alert_data["symbol"], alert_data["alert_type"], alert_data["triggered_at"]):
                        continue

                    alert = Alert(
                        symbol=alert_data['symbol'],
                        alert_type=alert_data['alert_type'],
                        severity=alert_data['severity'],
                        message=alert_data['message'],
                        triggered_at=_normalize_ts(alert_data['triggered_at']),
                        price_at_trigger=alert_data['price_at_trigger'],
                        percent_change=alert_data['percent_change'],
                    )
                    db.add(alert)
                    new_count += 1
                    alerts_generated += 1

                # Advance watermark so next run starts after this one
                stock.last_analyzed_at = datetime.utcnow()

                symbols_processed += 1
                logger.info(
                    f"Processed {symbol}: {new_count} new alerts "
                    f"({len(sharp_moves) + len(patterns)} candidates, first_run={is_first_run})"
                )

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")

        # Commit all changes
        db.commit()

        # Update analysis run record
        duration = (datetime.utcnow() - start_time).total_seconds()
        run.status = "completed"
        run.symbols_processed = symbols_processed
        run.alerts_generated = alerts_generated
        run.duration_seconds = duration
        db.commit()

        logger.info(f"=== Analysis job completed in {duration:.2f}s: {symbols_processed} symbols, {alerts_generated} alerts ===")
        return {"status": "success", "symbols": symbols_processed, "alerts": alerts_generated}

    except Exception as e:
        logger.error(f"Error in analysis job: {e}")
        run.status = "failed"
        run.error_message = str(e)
        db.commit()
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()


def get_latest_alerts(db: Session, limit: int = 50):
    """Get the most recent alerts."""
    alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
    return alerts


def get_stocks_status(db: Session):
    """Get current status of all monitored stocks."""
    stocks = db.query(Stock).all()
    return stocks


def cleanup_old_alerts(db: Session):
    """Clean up alerts older than retention period."""
    from datetime import timedelta

    retention_days = app_config.alert_retention_days
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    deleted = db.query(Alert).filter(Alert.created_at < cutoff_date).delete()
    db.commit()

    logger.info(f"Deleted {deleted} old alerts")
    return deleted
