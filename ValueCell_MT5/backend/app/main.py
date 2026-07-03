import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import dashboard, trading, agents, performance, websocket, valuecell, activity_logs
from app.config import get_settings
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging import LoggingMiddleware
from app.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info(f"[START] Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"[INFO] Environment: {settings.APP_ENV}")
    logger.info(f"[API] API Host: {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"[TRADING] Trading Mode: {settings.TRADING_MODE.upper()}")

    # Initialize MT5 connection
    mt5_manager = None
    # try:
    #     from app.core.mt5_manager import MT5Manager
    #     mt5_manager = MT5Manager()
    #     if mt5_manager.connect():
    #         logger.info("[OK] MT5 connection established")
    #     else:
    #         logger.warning("[WARNING] MT5 connection failed — running in degraded mode")
    # except Exception as e:
    #     logger.error(f"[ERROR] MT5 initialization error: {e}")

    # Initialize Neon PostgreSQL connection pool
    pipeline = None
    watcher = None
    try:
        from app.core.database import init_db_pool
        db_ready = init_db_pool(minconn=1, maxconn=5)
        if db_ready:
            logger.info("[DB] [OK] Neon PostgreSQL pool ready")

            # Start Track 1 real-time pipeline
            # from app.services.pipeline import Track1Pipeline
            # pipeline = Track1Pipeline(interval_seconds=settings.TRACK1_INTERVAL_SECONDS)
            # await pipeline.start()

            # Start Track 2 CSV Watcher Service
            from app.services.csv_watcher_service import CSVWatcherService
            watcher = CSVWatcherService(check_interval_seconds=5)
            watcher.start()
            logger.info("[Watcher] [OK] CSV Watcher Service started")
        else:
            logger.warning("[DB] [WARNING] Neon DB pool failed — Track 1 & Watcher pipeline NOT started")
    except Exception as e:
        logger.error(f"[DB] Pipeline startup error: {e}")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("[STOP] Shutting down application")

    # Stop CSV watcher
    if watcher is not None:
        try:
            watcher.stop()
            logger.info("[Watcher] CSV Watcher stopped")
        except Exception as e:
            logger.warning(f"[Watcher] Error stopping watcher: {e}")

    # Stop Track 1 pipeline
    if pipeline is not None:
        try:
            await pipeline.stop()
            logger.info("[Track1] Pipeline stopped")
        except Exception as e:
            logger.warning(f"[Track1] Error stopping pipeline: {e}")

    # Close DB pool
    try:
        from app.core.database import close_db_pool
        close_db_pool()
    except Exception:
        pass

    # Cleanup MT5 connection
    if mt5_manager is not None:
        try:
            mt5_manager.disconnect()
            logger.info("[OK] MT5 disconnected")
        except Exception:
            pass


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Professional MT5 trading dashboard with AI-powered market analysis - Divine Trading Precision",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(LoggingMiddleware)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.APP_NAME}",
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "docs": "/docs" if settings.DEBUG else None,
        }
    )


@app.get("/health")
@app.options("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "version": settings.APP_VERSION,
        }
    )


@app.get("/api/v1/health")
@app.options("/api/v1/health")
async def health_check_v1():
    """Health check endpoint for API v1."""
    return JSONResponse(
        content={
            "status": "healthy",
            "version": settings.APP_VERSION,
        }
    )


# Include routers
app.include_router(
    dashboard.router,
    prefix=f"{settings.API_V1_PREFIX}/dashboard",
    tags=["Dashboard"],
)

app.include_router(
    trading.router,
    prefix=f"{settings.API_V1_PREFIX}/trading",
    tags=["Trading"],
)

app.include_router(
    agents.router,
    prefix=f"{settings.API_V1_PREFIX}/agents",
    tags=["Agents"],
)

app.include_router(
    performance.router,
    prefix=f"{settings.API_V1_PREFIX}/performance",
    tags=["Performance"],
)

app.include_router(
    activity_logs.router,
    prefix=f"{settings.API_V1_PREFIX}/activity-logs",
    tags=["Activity Logs"],
)

app.include_router(
    websocket.router,
    prefix=f"{settings.API_V1_PREFIX}/ws",
    tags=["WebSocket"],
)

# ValueCell legacy endpoints (for backward compatibility)
app.include_router(
    valuecell.router,
    tags=["Legacy Compatibility"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
