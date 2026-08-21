import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.data.fetcher import StockDataFetcher
from app.data.cache import cache
from app.analysis.volatility import VolatilityAnalyzer
from app.database.models import Alert, AnalysisRun, Stock
from app.database.connection import SessionLocal
from app.config import app_config

logger = logging.getLogger(__name__)


def run_analysis_job():
    """
    Main scheduled job to fetch data, run analysis, and generate alerts.
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

        for symbol in symbols:
            try:
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

                stock.last_price = float(data['Close'].iloc[-1])
                stock.last_update = datetime.utcnow()

                # Run analysis
                sharp_moves = analyzer.detect_sharp_moves(data, symbol)
                patterns = analyzer.detect_volatility_patterns(data, symbol)

                all_alerts = sharp_moves + patterns

                # Store alerts in database
                for alert_data in all_alerts:
                    alert = Alert(
                        symbol=alert_data['symbol'],
                        alert_type=alert_data['alert_type'],
                        severity=alert_data['severity'],
                        message=alert_data['message'],
                        triggered_at=alert_data['triggered_at'],
                        price_at_trigger=alert_data['price_at_trigger'],
                        percent_change=alert_data['percent_change'],
                    )
                    db.add(alert)
                    alerts_generated += 1

                symbols_processed += 1
                logger.info(f"Processed {symbol}: {len(all_alerts)} alerts generated")

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
    from sqlalchemy import func
    from datetime import datetime, timedelta

    retention_days = app_config.alert_retention_days
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    deleted = db.query(Alert).filter(Alert.created_at < cutoff_date).delete()
    db.commit()

    logger.info(f"Deleted {deleted} old alerts")
    return deleted
