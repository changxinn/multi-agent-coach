"""
FastAPI application entry point.

Configures middleware, routes, and lifecycle events.
"""

import asyncio
import logging
import string
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.request_context import request_id
from app.api.routes import auth, chat, nutrition, session
from app.config import get_settings
from app.db.database import close_db, engine, init_db
from app.services.nutrition_agent_client import nutrition_agent_client
from app.services.session_manager import session_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Initialize database
    await init_db()

    # Start session cleanup task
    cleanup_task = await session_manager.start_cleanup_task(interval_hours=1)
    await nutrition_agent_client.start()

    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Close database connections
    await nutrition_agent_client.close()
    await close_db()

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Multi-Agent Fitness Coach API with LangGraph",
    lifespan=lifespan,
)


def is_nutrition_request(request: Request) -> bool:
    """Limit the canonical Nutrition error contract to the Nutrition surface."""
    return request.url.path.startswith("/api/nutrition")


def valid_request_id(value: str | None) -> bool:
    return (
        bool(value)
        and len(value) <= 128
        and all(char in string.printable and not char.isspace() for char in value)
    )


def nutrition_error(
    status_code: int, code: str, message: str, request: Request
) -> JSONResponse:
    identifier = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": identifier}},
        headers={"X-Request-ID": identifier},
    )


NUTRITION_NOT_FOUND_CODES = {
    "NUTRITION_PROFILE_NOT_FOUND",
    "MEAL_LOG_NOT_FOUND",
    "NUTRITION_TARGET_NOT_FOUND",
    "FOOD_NOT_FOUND",
    "ASSESSMENT_NOT_FOUND",
}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    identifier = request.headers.get("X-Request-ID")
    identifier = identifier if valid_request_id(identifier) else str(uuid.uuid4())
    request.state.request_id = identifier
    token = request_id.set(identifier)
    try:
        response = await call_next(request)
    finally:
        request_id.reset(token)
    response.headers["X-Request-ID"] = identifier
    return response


@app.exception_handler(RequestValidationError)
async def nutrition_validation_error(request: Request, exc: RequestValidationError):
    if is_nutrition_request(request):
        return nutrition_error(
            422, "VALIDATION_ERROR", "Request validation failed.", request
        )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(HTTPException)
async def nutrition_http_error(request: Request, exc: HTTPException):
    if not is_nutrition_request(request):
        return await http_exception_handler(request, exc)
    if exc.status_code == 401:
        return nutrition_error(
            401, "UNAUTHORIZED", "Authentication is required.", request
        )
    if exc.status_code == 403:
        return nutrition_error(
            403, "FORBIDDEN", "You are not allowed to perform this action.", request
        )
    if exc.status_code == 404:
        code = (
            exc.detail.get("code")
            if isinstance(exc.detail, dict) and exc.detail.get("code") in NUTRITION_NOT_FOUND_CODES
            else "FOOD_NOT_FOUND"
        )
        return nutrition_error(
            404,
            code,
            "The requested nutrition resource was not found.",
            request,
        )
    if exc.status_code == 422:
        if isinstance(exc.detail, dict) and exc.detail.get("code") in {
            "VALIDATION_ERROR",
            "NUTRITION_SAFETY_REFERRAL_REQUIRED",
            "NUTRITION_VALUE_INCONSISTENT",
        }:
            code = exc.detail["code"]
            return nutrition_error(
                422,
                code,
                (
                    str(exc.detail.get("message"))
                    if code in {
                        "NUTRITION_SAFETY_REFERRAL_REQUIRED",
                        "VALIDATION_ERROR",
                    }
                    else "Nutrition values are inconsistent."
                ),
                request,
            )
        return nutrition_error(
            422, "VALIDATION_ERROR", "Request validation failed.", request
        )
    if exc.status_code == 503:
        return nutrition_error(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "Nutrition service is temporarily unavailable.",
            request,
        )
    return nutrition_error(
        exc.status_code, "INTERNAL_ERROR", "An unexpected error occurred.", request
    )


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(session.router, prefix="/api", tags=["Session"])
app.include_router(nutrition.router, prefix="/api", tags=["Nutrition"])


# Health check endpoints
@app.get("/health/live", tags=["Health"])
async def health_live():
    """Dependency-free liveness probe."""
    return {"status": "live"}


def _configuration_ready() -> bool:
    """Check readiness configuration without returning its values."""
    database = urlparse(settings.DATABASE_URL)
    if database.scheme not in {"postgresql", "postgresql+asyncpg"} or not database.netloc:
        return False
    if not settings.DATABASE_SCHEMA or not settings.NUTRITION_INTERNAL_SERVICE_TOKEN:
        return False
    if settings.USE_NUTRITION_AGENT_SERVICE:
        nutrition_url = urlparse(settings.NUTRITION_AGENT_URL)
        if nutrition_url.scheme not in {"http", "https"} or not nutrition_url.netloc:
            return False
    return True


@app.get("/health/ready", tags=["Health"])
async def health_ready():
    """Report sanitized configuration, database, and schema readiness."""
    checks = {"configuration": "failed", "database": "failed", "schema": "failed"}
    if _configuration_ready():
        checks["configuration"] = "ok"
        try:
            from sqlalchemy import text

            async with engine.begin() as connection:
                await connection.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            logger.warning("Main API readiness database check failed")
        if checks["database"] == "ok":
            try:
                from app.db.migrate import validate_compatible_schema

                if (await validate_compatible_schema()).compatible:
                    checks["schema"] = "ok"
            except Exception:
                logger.warning("Main API readiness schema check failed")
    status_code = 200 if all(value == "ok" for value in checks.values()) else 503
    return JSONResponse(status_code=status_code, content={"status": "ready", "checks": checks})


@app.get("/health", tags=["Health"])
async def health_check():
    """Deprecated compatibility alias for the liveness probe."""
    return await health_live()


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
