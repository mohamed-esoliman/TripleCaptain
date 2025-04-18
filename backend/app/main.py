from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging
import time

from app.core.config import settings
from app.api import auth, players, teams, predictions, optimization, admin
from app.api import team as team_api
from app.api import fixtures as fixtures_api
from app.api import squads as squads_api
from app.api import analytics as analytics_api
from app.core.security import SecurityError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # Start background tasks
    if settings.ENVIRONMENT == "production":
        from app.services.background_tasks import task_manager

        await task_manager.start_scheduled_tasks()
        logger.info("Background tasks started")

    yield

    # Shutdown
    if settings.ENVIRONMENT == "production":
        from app.services.background_tasks import task_manager

        await task_manager.stop_scheduled_tasks()
        logger.info("Background tasks stopped")

    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS middleware (open in development for reliability)
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if settings.ENVIRONMENT != "production" else settings.ALLOWED_ORIGINS
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware for production
if settings.ENVIRONMENT == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to all responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handlers
@app.exception_handler(SecurityError)
async def security_exception_handler(request: Request, exc: SecurityError):
    """Handle security exceptions."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()},
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(players.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")
app.include_router(optimization.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(fixtures_api.router, prefix="/api/v1")
app.include_router(squads_api.router, prefix="/api/v1")
app.include_router(analytics_api.router, prefix="/api/v1")
app.include_router(team_api.router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "docs_url": "/docs",
        "health_check": "/health",
    }


# API info endpoint
@app.get("/api/v1")
async def api_info():
    """API version information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "endpoints": {
            "authentication": "/api/v1/auth",
            "players": "/api/v1/players",
            "fixtures": "/api/v1/fixtures",
            "predictions": "/api/v1/predictions",
            "optimization": "/api/v1/optimization",
            "squads": "/api/v1/squads",
            "analytics": "/api/v1/analytics",
            "team": "/api/v1/team",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )
