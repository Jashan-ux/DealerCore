import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every incoming request and outgoing response.

    For each request it records:
    - A unique request_id (UUID) that ties the request and response logs together
    - HTTP method and path
    - Client IP address
    - Response status code
    - Total processing time in milliseconds

    The request_id is also added to the response headers so that clients
    can include it in bug reports, making it trivial to find the exact
    request in your logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())

        # Bind the request_id to structlog's context vars so it appears
        # in every log line produced during this request's lifetime,
        # even in logs from service and repository layers
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()

        # Log the incoming request
        logger.info(
            "request_started",
            method=request.method,
            path=str(request.url.path),
            query_params=str(request.query_params),
            client_ip=request.client.host if request.client else "unknown",
        )

        # Process the request through the rest of the middleware stack
        # and into the route handler
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log unhandled exceptions before re-raising
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed_unhandled_exception",
                method=request.method,
                path=str(request.url.path),
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                exc_info=True,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log the completed response
        logger.info(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add the request_id to the response headers so clients can
        # reference it when reporting issues
        response.headers["X-Request-ID"] = request_id

        return response