"""Logging configuration."""

import logging
import sys
from pathlib import Path
from loguru import logger
from app.config import get_settings

settings = get_settings()


class InterceptHandler(logging.Handler):
    """Logs standard logging messages via loguru."""

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    """Setup application logging."""
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Configure loguru handlers
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | {message}",
    )
    logger.add(
        log_dir / "app.log",
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
        rotation="10 MB",
    )

    # Configure root logger with InterceptHandler
    logging.basicConfig(
        handlers=[InterceptHandler()],
        level=getattr(logging, settings.LOG_LEVEL),
        force=True,
    )

    # Route specific loggers to warnings if needed or let them flow
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("fastapi").handlers = [InterceptHandler()]
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
