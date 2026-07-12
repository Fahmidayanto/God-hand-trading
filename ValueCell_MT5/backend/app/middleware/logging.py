"""Logging middleware."""

import logging
import time
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Log request and response."""
        # Start timer
        start_time = time.time()

        # Check if path or method is quiet
        is_quiet = False
        if request.method == "OPTIONS":
            is_quiet = True
        else:
            path = request.url.path
            quiet_prefixes = [
                "/api/v1/health",
                "/api/v1/dashboard/",
                "/api/v1/trading/positions",
                "/api/v1/trading/signal",
                "/api/v1/trading/replay/months",
                "/api/v1/scenarios",
                "/api/v1/activity-logs",
                "/api/v1/agents/",
                "/api/v1/performance/",
                "/api/v1/conversations/",
                "/api/v1/trading/replay",
                "/api/v1/trading/chart/rongsokan-data",
                "/api/v1/trading/session-zones",
                "/api/v1/trading/trades/history",
                "/api/v1/trading/simulate-event",
            ]
            if any(path.startswith(prefix) for prefix in quiet_prefixes):
                is_quiet = True

        # Log request
        if not is_quiet:
            logger.info(
                f"-> {request.method} {request.url.path} "
                f"from {request.client.host if request.client else 'unknown'}"
            )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response (only if not quiet OR if it's an error status code)
        if not is_quiet or response.status_code >= 400:
            log_level = logging.INFO if response.status_code < 400 else logging.WARNING
            logger.log(
                log_level,
                f"<- {request.method} {request.url.path} "
                f"status={response.status_code} duration={duration:.3f}s"
            )

        # Add timing header
        response.headers["X-Process-Time"] = f"{duration:.3f}"

        return response
