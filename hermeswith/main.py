"""FastAPI main application for Hermeswith."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hermeswith.api.middleware import (
    AuditMiddleware,
    RateLimitMiddleware,
    TenantIsolationMiddleware,
    TimingMiddleware,
)
from hermeswith.api.router import router
from hermeswith.config import settings
from hermeswith.persistence.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting up Hermeswith API...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Hermeswith API...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Hermeswith API",
        description="Multi-tenant agent management API for Clawith integration",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.add_middleware(TimingMiddleware)
    app.add_middleware(TenantIsolationMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)
    app.add_middleware(AuditMiddleware)
    
    # Include routers
    app.include_router(router, prefix="")
    
    return app


# Create application instance
app = create_app()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Hermeswith API",
        "version": "0.1.0",
        "docs": "/docs",
    }
