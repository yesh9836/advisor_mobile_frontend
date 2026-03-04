"""
Sentry initialization and capture helpers.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - dependency may be unavailable in minimal local envs
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except Exception:  # pragma: no cover - defensive fallback
    sentry_sdk = None
    FastApiIntegration = None


def _has_active_client() -> bool:
    if sentry_sdk is None:
        return False
    client = sentry_sdk.get_client()
    return client is not None and client.options.get("dsn") is not None


def _build_init_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "dsn": settings.SENTRY_DSN,
        "environment": settings.SENTRY_ENVIRONMENT or settings.APP_ENV,
        "release": settings.SENTRY_RELEASE or settings.APP_VERSION,
        "send_default_pii": settings.SENTRY_SEND_DEFAULT_PII,
        "attach_stacktrace": settings.SENTRY_ATTACH_STACKTRACE,
        "traces_sample_rate": settings.SENTRY_TRACES_SAMPLE_RATE,
        "profiles_sample_rate": settings.SENTRY_PROFILES_SAMPLE_RATE,
        "max_breadcrumbs": settings.SENTRY_MAX_BREADCRUMBS,
    }
    return kwargs


def _build_fastapi_integration() -> Any | None:
    if FastApiIntegration is None:
        return None
    try:
        signature = inspect.signature(FastApiIntegration.__init__)
        if "transaction_style" in signature.parameters:
            return FastApiIntegration(transaction_style="endpoint")
        return FastApiIntegration()
    except Exception:
        return FastApiIntegration()


def init_sentry(*, service_name: str, with_fastapi_integration: bool = False) -> bool:
    """
    Initialize Sentry if DSN and SDK are available.
    """
    if not settings.SENTRY_DSN:
        return False
    if sentry_sdk is None:
        logger.warning("Sentry DSN is configured but sentry_sdk is not installed.")
        return False

    init_kwargs = _build_init_kwargs()
    integrations: list[Any] = []
    if with_fastapi_integration:
        fastapi_integration = _build_fastapi_integration()
        if fastapi_integration is not None:
            integrations.append(fastapi_integration)
    if integrations:
        init_kwargs["integrations"] = integrations

    sentry_sdk.init(**init_kwargs)
    sentry_sdk.set_tag("service", service_name)
    sentry_sdk.set_tag("app_env", settings.APP_ENV)
    sentry_sdk.set_tag("app_name", settings.APP_NAME)
    return True


def capture_exception(
    exc: BaseException,
    *,
    tags: dict[str, str] | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """
    Capture an exception only when Sentry is active.
    """
    if sentry_sdk is None or not _has_active_client():
        return
    with sentry_sdk.push_scope() as scope:
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, value)
        if context:
            scope.set_context("details", context)
        sentry_sdk.capture_exception(exc)
