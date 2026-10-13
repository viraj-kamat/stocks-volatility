import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.routes import api
from app.routes import auth as auth_routes
from app.routes import logs as logs_routes
from app.routes.static import serve_static
from app.config import app_config, settings
from app.auth import AuthMiddleware, auth_enabled

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting StockSpikes")
    logger.info(f"Monitored symbols: {app_config.symbols}")
    logger.info(f"Volatility threshold: {app_config.volatility_threshold}%")
    if auth_enabled():
        logger.info("Password authentication enabled (STOCKSPIKES_PWD)")
    else:
        logger.warning("STOCKSPIKES_PWD is not set — dashboard auth is disabled")

    if settings.alpaca_api_key and settings.alpaca_api_secret:
        logger.info("Alpaca live quotes enabled (feed=%s)", settings.alpaca_data_feed or "auto")
    else:
        logger.warning("Alpaca keys missing — live quotes are unavailable")

    yield

    # Shutdown
    logger.info("Shutting down StockSpikes")


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

# Password gate (cookie session). Added last so it runs first.
app.add_middleware(AuthMiddleware)

# Include routes
app.include_router(auth_routes.router)
app.include_router(api.router)
app.include_router(logs_routes.router)

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
