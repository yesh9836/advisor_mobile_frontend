from contextlib import asynccontextmanager
import logging
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import uvicorn

from app.api.v1 import api_router
from app.core.config import settings
from app.core.rate_limit import (
    get_rate_limiter_status_snapshot,
    init_rate_limiter,
    is_rate_limiter_critical_unavailable,
    shutdown_rate_limiter,
)
from app.core.sentry import init_sentry
from app.db.session import SessionLocal
from app.services.notification_outbox_health_service import NotificationOutboxHealthService
from app.services.stripe_webhook_health_service import StripeWebhookHealthService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
_SENSITIVE_HEALTH_FIELDS = frozenset({"error", "last_error"})


def _redact_health_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_health_payload(item)
            for key, item in value.items()
            if key not in _SENSITIVE_HEALTH_FIELDS
        }
    if isinstance(value, list):
        return [_redact_health_payload(item) for item in value]
    return value


def _resolve_openapi_docs_config() -> tuple[Optional[str], Optional[str], Optional[str]]:
    docs_allowed = settings.API_DOCS_ENABLED and (
        not settings.is_production or settings.API_DOCS_IN_PRODUCTION
    )
    if not docs_allowed:
        return None, None, None
    return "/api/openapi.json", "/api/docs", "/api/redoc"


def _check_database_readiness() -> dict[str, object]:
    timeout_seconds = max(float(settings.HEALTH_READY_DB_TIMEOUT_SECONDS), 0.1)
    timeout_ms = max(int(timeout_seconds * 1000), 1)
    db = SessionLocal()
    try:
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        probe_query = "SELECT 1"
        if dialect_name == "mysql":
            probe_query = f"SELECT /*+ MAX_EXECUTION_TIME({timeout_ms}) */ 1"
        elif dialect_name == "postgresql":
            db.execute(text("SET LOCAL statement_timeout = :timeout_ms"), {"timeout_ms": timeout_ms})
        db.execute(text(probe_query)).scalar_one()
        return {
            "status": "healthy",
            "timeout_seconds": timeout_seconds,
        }
    except Exception as exc:
        logger.exception("Database readiness probe failed: %s", exc)
        return {
            "status": "unhealthy",
            "timeout_seconds": timeout_seconds,
            "error": str(exc),
        }
    finally:
        db.close()


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
init_sentry(service_name="backend-api", with_fastapi_integration=True)

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
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/live")
def health_live():
    return {"status": "healthy"}


@app.get("/health/ready")
def health_ready():
    limiter_status = get_rate_limiter_status_snapshot()
    status_text = "unhealthy" if is_rate_limiter_critical_unavailable() else "healthy"
    database_status = _check_database_readiness()
    database_available = database_status.get("status") == "healthy"
    if not database_available:
        status_text = "unhealthy"
    notification_pipeline_status = {
        "status": "skipped",
        "enabled": bool(settings.NOTIFICATIONS_ENABLED),
    }
    if settings.NOTIFICATIONS_ENABLED and database_available:
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
    elif settings.NOTIFICATIONS_ENABLED and not database_available:
        notification_pipeline_status = {
            "status": "skipped",
            "enabled": True,
            "reason": "database_unavailable",
        }
    webhook_pipeline_status = {
        "status": "skipped",
        "enabled": bool(settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED),
    }
    cleanup_pipeline_status = {
        "status": "skipped",
        "enabled": bool(settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED),
    }
    if settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED and database_available:
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
        db = SessionLocal()
        try:
            pipeline_snapshot = StripeWebhookHealthService.get_cleanup_pipeline_health_snapshot(db)
            cleanup_pipeline_status = {
                "status": pipeline_snapshot.get("status", "unhealthy"),
                "enabled": True,
                **pipeline_snapshot,
            }
            if cleanup_pipeline_status["status"] != "healthy":
                status_text = "unhealthy"
        except Exception as exc:
            logger.exception("Failed to evaluate Stripe cleanup outbox readiness: %s", exc)
            status_text = "unhealthy"
            cleanup_pipeline_status = {
                "status": "unhealthy",
                "enabled": True,
                "breaches": ["health_snapshot_error"],
                "error": str(exc),
            }
        finally:
            db.close()
    elif settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED and not database_available:
        webhook_pipeline_status = {
            "status": "skipped",
            "enabled": True,
            "reason": "database_unavailable",
        }
        cleanup_pipeline_status = {
            "status": "skipped",
            "enabled": True,
            "reason": "database_unavailable",
        }
    payload = {
        "status": status_text,
        "checks": {
            "database": database_status,
            "rate_limiter": limiter_status,
            "notification_outbox_pipeline": notification_pipeline_status,
            "stripe_webhook_pipeline": webhook_pipeline_status,
            "stripe_cleanup_outbox_pipeline": cleanup_pipeline_status,
        },
    }
    public_payload = _redact_health_payload(payload)
    if status_text != "healthy":
        return JSONResponse(status_code=503, content=public_payload)
    return public_payload


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
