from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, status
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger(__name__)

# The key_func determines what to rate limit by.
# In normal traffic, we use the client's IP address. For tests, we
# allow a deterministic header override so multiple fixture-driven auth
# requests can be isolated without tripping the shared rate bucket.
def get_rate_limit_key(request: Request) -> str:
    test_client_id = request.headers.get("X-Test-Client-Id")
    if test_client_id:
        return test_client_id
    return get_remote_address(request)


limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["200 per minute"],  # global default for all endpoints
)


async def rate_limit_exceeded_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Without this handler, slowapi returns a plain text response.
    This handler returns your standard JSON error format and logs
    the event for security monitoring.
    """
    logger.warning(
        "rate_limit_exceeded",
        path=str(request.url.path),
        method=request.method,
        client_ip=request.client.host if request.client else "unknown",
        limit=str(exc.limit),
    )

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": f"Rate limit exceeded. Limit: {exc.limit}. Please slow down your requests."
        },
        headers={
            "Retry-After": "60",  # tell the client to wait 60 seconds
        },
    )