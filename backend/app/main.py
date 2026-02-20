"""
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
import logging
from typing import Optional

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
from app.db.session import SessionLocal
from app.services.notification_outbox_health_service import NotificationOutboxHealthService
from app.services.stripe_webhook_health_service import StripeWebhookHealthService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def _resolve_openapi_docs_config() -> tuple[Optional[str], Optional[str], Optional[str]]:
    docs_allowed = settings.API_DOCS_ENABLED and (
        not settings.is_production or settings.API_DOCS_IN_PRODUCTION
    )
    if not docs_allowed:
        return None, None, None
    return "/api/openapi.json", "/api/docs", "/api/redoc"


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    await init_rate_limiter()
    try:
        yield
    finally:
        await shutdown_rate_limiter()


openapi_url, docs_url, redoc_url = _resolve_openapi_docs_config()

app = FastAPI(
    title=settings.APP_NAME,
    description="One-time lead purchase platform for financial advisors to receive retirement planning leads",
    version="1.0.0",
    openapi_url=openapi_url,
    docs_url=docs_url,
    redoc_url=redoc_url,
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
    notification_pipeline_status = {
        "status": "skipped",
        "enabled": bool(settings.NOTIFICATIONS_ENABLED),
    }
    if settings.NOTIFICATIONS_ENABLED:
        db = SessionLocal()
        try:
            pipeline_snapshot = NotificationOutboxHealthService.get_pipeline_health_snapshot(db)
            notification_pipeline_status = {
                "status": pipeline_snapshot.get("status", "unhealthy"),
                "enabled": True,
                **pipeline_snapshot,
            }
            if notification_pipeline_status["status"] != "healthy":
                status_text = "unhealthy"
        except Exception as exc:
            logger.exception("Failed to evaluate notification outbox readiness: %s", exc)
            status_text = "unhealthy"
            notification_pipeline_status = {
                "status": "unhealthy",
                "enabled": True,
                "breaches": ["health_snapshot_error"],
                "error": str(exc),
            }
        finally:
            db.close()
    webhook_pipeline_status = {
        "status": "skipped",
        "enabled": bool(settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED),
    }
    if settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED:
        db = SessionLocal()
        try:
            pipeline_snapshot = StripeWebhookHealthService.get_pipeline_health_snapshot(db)
            webhook_pipeline_status = {
                "status": pipeline_snapshot.get("status", "unhealthy"),
                "enabled": True,
                **pipeline_snapshot,
            }
            if webhook_pipeline_status["status"] != "healthy":
                status_text = "unhealthy"
        except Exception as exc:
            logger.exception("Failed to evaluate Stripe webhook pipeline readiness: %s", exc)
            status_text = "unhealthy"
            webhook_pipeline_status = {
                "status": "unhealthy",
                "enabled": True,
                "breaches": ["health_snapshot_error"],
                "error": str(exc),
            }
        finally:
            db.close()
    payload = {
        "status": status_text,
        "checks": {
            "rate_limiter": limiter_status,
            "notification_outbox_pipeline": notification_pipeline_status,
            "stripe_webhook_pipeline": webhook_pipeline_status,
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
