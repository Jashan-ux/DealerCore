import structlog
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError

logger = structlog.get_logger(__name__)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle Pydantic validation errors from request parsing.

    FastAPI raises RequestValidationError when request data fails
    Pydantic schema validation. The default FastAPI handler returns
    the raw Pydantic error structure which is verbose and inconsistent.
    This handler reformats it into your application's standard error shape.
    """
    # Extract human-readable error messages from Pydantic's error list
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    logger.warning(
        "request_validation_failed",
        path=str(request.url.path),
        method=request.method,
        errors=errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": errors,
        },
    )


async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    """
    Handle database integrity errors such as unique constraint violations.

    SQLAlchemy raises IntegrityError when a database constraint is violated.
    The raw exception message contains table names and constraint names that
    you should never expose to clients. This handler maps it to a safe message.
    """
    logger.error(
        "database_integrity_error",
        path=str(request.url.path),
        method=request.method,
        # Log the full error internally for debugging
        db_error=str(exc.orig),
    )

    # Detect the specific violation type from the PostgreSQL error code
    # to give a more helpful message without leaking schema details
    error_message = "A record with conflicting data already exists"
    if exc.orig and hasattr(exc.orig, "pgcode"):
        if exc.orig.pgcode == "23505":  # unique_violation
            error_message = "A record with this data already exists"
        elif exc.orig.pgcode == "23503":  # foreign_key_violation
            error_message = "Referenced record does not exist"
        elif exc.orig.pgcode == "23514":  # check_violation
            error_message = "Data violates a business rule constraint"

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": error_message},
    )


async def operational_error_handler(
    request: Request,
    exc: OperationalError,
) -> JSONResponse:
    """
    Handle database connection and operational errors.

    OperationalError covers cases like the database being unreachable,
    connection pool exhaustion, and query timeouts.
    """
    logger.error(
        "database_operational_error",
        path=str(request.url.path),
        method=request.method,
        db_error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": "The service is temporarily unavailable. Please try again shortly."
        },
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catch-all handler for any exception not caught by more specific handlers.

    This is the safety net. If this handler fires, it means an exception
    type was not anticipated. Log everything for debugging, return nothing
    useful to the client.
    """
    logger.error(
        "unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Our team has been notified."
        },
    )