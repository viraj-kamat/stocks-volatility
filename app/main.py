import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from contextlib import asynccontextmanager
import os

from app.routes import api
from app.routes.static import serve_static
from app.config import app_config, settings
from app.scheduler.jobs import run_analysis_job, cleanup_old_alerts
from app.database.connection import SessionLocal

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global scheduler
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting StockSpikes")
    logger.info(f"Monitored symbols: {app_config.symbols}")
    logger.info(f"Volatility threshold: {app_config.volatility_threshold}%")

    # Start scheduler
    if not scheduler.running:
        interval_hours = app_config.scheduler_interval_hours
        scheduler.add_job(
            run_analysis_job,
            'interval',
            hours=interval_hours,
            id='analysis_job',
            name='Stock Analysis Job',
            replace_existing=True,
        )

        # Also run cleanup job daily
        scheduler.add_job(
            cleanup_old_alerts_wrapper,
            'interval',
            hours=24,
            id='cleanup_job',
            name='Alert Cleanup Job',
            replace_existing=True,
        )

        scheduler.start()
        logger.info(f"Scheduler started with {interval_hours}h interval")

    # Run initial analysis
    try:
        logger.info("Running initial analysis...")
        run_analysis_job()
    except Exception as e:
        logger.error(f"Initial analysis failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down StockSpikes")
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def cleanup_old_alerts_wrapper():
    """Wrapper for cleanup job to handle database session."""
    db = SessionLocal()
    try:
        cleanup_old_alerts(db)
    finally:
        db.close()


app = FastAPI(
    title="StockSpikes",
    description="Monitor stock price volatility and detect sharp movements",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(api.router)

# Serve static files
serve_static(app)


@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
