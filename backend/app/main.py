"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from app.api.v1 import api_router
from app.core.config import settings
from app.core.rate_limit import (
    get_rate_limiter_status_snapshot,
    init_rate_limiter,
    is_rate_limiter_critical_unavailable,
    shutdown_rate_limiter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    await init_rate_limiter()
    try:
        yield
    finally:
        await shutdown_rate_limiter()


app = FastAPI(
    title=settings.APP_NAME,
    description="One-time lead purchase platform for financial advisors to receive retirement planning leads",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=app_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Backward-compatible liveness endpoint."""
    return {"status": "healthy"}


@app.get("/health/live")
def health_live():
    """Liveness endpoint."""
    return {"status": "healthy"}


@app.get("/health/ready")
def health_ready():
    """Readiness endpoint."""
    limiter_status = get_rate_limiter_status_snapshot()
    status_text = "unhealthy" if is_rate_limiter_critical_unavailable() else "healthy"
    payload = {
        "status": status_text,
        "checks": {
            "rate_limiter": limiter_status,
        },
    }
    if status_text != "healthy":
        return JSONResponse(status_code=503, content=payload)
    return payload


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
