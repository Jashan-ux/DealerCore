import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.v1 import audit, auth, purchases, vehicles
from app.core.config import get_settings
from app.core.exception_handlers import (
    generic_exception_handler,
    integrity_error_handler,
    operational_error_handler,
    validation_exception_handler,
)
from app.core.logging_config import configure_logging, get_logger
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler
from app.middleware.logging_middleware import RequestLoggingMiddleware

settings = get_settings()

# Configure logging before anything else runs
configure_logging(debug=settings.DEBUG)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager replaces the deprecated on_event handlers.
    Code before yield runs on startup.
    Code after yield runs on shutdown.
    """
    logger.info(
        "application_starting",
        app_name=settings.APP_NAME,
        debug=settings.DEBUG,
    )
    yield
    logger.info("application_shutting_down")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Production-grade Car Dealership Inventory API. "
        "Manage vehicles, process purchases, and track inventory."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ------------------------------------------------------------------ #
# Rate limiter state must be attached to app before middleware
# ------------------------------------------------------------------ #
app.state.limiter = limiter

# ------------------------------------------------------------------ #
# Middleware — order matters: added last runs first
# ------------------------------------------------------------------ #

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

# ------------------------------------------------------------------ #
# Exception handlers
# ------------------------------------------------------------------ #

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(OperationalError, operational_error_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ------------------------------------------------------------------ #
# Routers
# ------------------------------------------------------------------ #

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(vehicles.router, prefix=settings.API_V1_PREFIX)
app.include_router(purchases.router, prefix=settings.API_V1_PREFIX)
app.include_router(audit.router, prefix=settings.API_V1_PREFIX)


# ------------------------------------------------------------------ #
# Health check
# ------------------------------------------------------------------ #

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "1.0.0",
    }