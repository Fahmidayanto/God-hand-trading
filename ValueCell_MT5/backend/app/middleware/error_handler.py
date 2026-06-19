"""Error handling middleware."""

import logging
from typing import Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler middleware."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Handle all exceptions."""
        try:
            response = await call_next(request)
            return response
        
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "error": "Validation Error",
                    "message": str(e),
                    "path": request.url.path,
                },
            )
        
        except PermissionError as e:
            logger.error(f"Permission error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Permission Denied",
                    "message": str(e),
                    "path": request.url.path,
                },
            )
        
        except ConnectionError as e:
            logger.error(f"Connection error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "Service Unavailable",
                    "message": "MT5 connection error",
                    "path": request.url.path,
                },
            )
        
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "path": request.url.path,
                },
            )
