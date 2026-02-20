from __future__ import annotations

import inspect
import logging
from collections import Counter
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from threading import Lock
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings

try:
    from fastapi_limiter import FastAPILimiter
    from fastapi_limiter.depends import RateLimiter
except (ModuleNotFoundError, ImportError):  # pragma: no cover - handled by availability checks
    try:
        # Some package builds expose FastAPILimiter only from a submodule.
        from fastapi_limiter.fastapi_limiter import FastAPILimiter  # type: ignore[attr-defined]
        from fastapi_limiter.depends import RateLimiter  # type: ignore[assignment]
    except (ModuleNotFoundError, ImportError):
        FastAPILimiter = None
        RateLimiter = None

try:
    from redis import asyncio as redis_asyncio
except ModuleNotFoundError:  # pragma: no cover - handled by availability checks
    redis_asyncio = None

logger = logging.getLogger(__name__)

RateLimitDependency = Callable[[Request, Response], Awaitable[None]]


class _RateLimitMetrics:
    """In-process counters for basic rate-limit observability."""

    def __init__(self) -> None:
        self._counts: Counter[tuple[str, str]] = Counter()
        self._lock = Lock()

    def increment(self, endpoint: str, reason: str) -> int:
        with self._lock:
            self._counts[(endpoint, reason)] += 1
            return self._counts[(endpoint, reason)]

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                f"{endpoint}:{reason}": count
                for (endpoint, reason), count in self._counts.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()


@dataclass
class _LimiterState:
    redis_client: Any | None = None
    ready: bool = False


_STATE = _LimiterState()
_METRICS = _RateLimitMetrics()


def _is_redis_backend_enabled() -> bool:
    return settings.RATE_LIMIT_ENABLED and settings.RATE_LIMIT_BACKEND == "redis"


def rate_limit_dependencies_available() -> bool:
    return FastAPILimiter is not None and RateLimiter is not None and redis_asyncio is not None


async def _init_fastapi_limiter(redis_client: Any) -> None:
    """
    Initialize FastAPILimiter across package-version API variants.
    """
    init_signature = inspect.signature(FastAPILimiter.init)
    init_params = init_signature.parameters
    init_kwargs: dict[str, Any] = {}

    if "prefix" in init_params:
        init_kwargs["prefix"] = settings.RATE_LIMIT_PREFIX
    if "identifier" in init_params:
        init_kwargs["identifier"] = _async_client_ip_identifier

    await FastAPILimiter.init(redis_client, **init_kwargs)

    # Backward compatibility when init() cannot receive identifier/prefix kwargs.
    if "identifier" not in init_params and hasattr(FastAPILimiter, "identifier"):
        setattr(FastAPILimiter, "identifier", _async_client_ip_identifier)
    if "prefix" not in init_params and hasattr(FastAPILimiter, "prefix"):
        setattr(FastAPILimiter, "prefix", settings.RATE_LIMIT_PREFIX)


def _build_rate_limiter(times: int, seconds: int) -> Any:
    """
    Construct RateLimiter across package-version API variants.
    """
    limiter_signature = inspect.signature(RateLimiter.__init__)
    limiter_params = limiter_signature.parameters
    limiter_kwargs: dict[str, Any] = {"times": times}

    if "seconds" in limiter_params:
        limiter_kwargs["seconds"] = seconds
    elif "milliseconds" in limiter_params:
        limiter_kwargs["milliseconds"] = seconds * 1000
    elif "minutes" in limiter_params:
        limiter_kwargs["minutes"] = max(1, (seconds + 59) // 60)
    if "identifier" in limiter_params:
        limiter_kwargs["identifier"] = _async_client_ip_identifier

    return RateLimiter(**limiter_kwargs)


async def _invoke_rate_limiter(limiter: Any, request: Request, response: Response) -> None:
    """
    Invoke RateLimiter across package-version call-signature variants.
    """
    call_signature = inspect.signature(limiter.__call__)
    call_params = call_signature.parameters

    if "response" in call_params:
        await limiter(request, response)
        return

    await limiter(request)


def _record_metric(endpoint: str, reason: str) -> None:
    _METRICS.increment(endpoint, reason)


def get_rate_limit_metrics_snapshot() -> dict[str, int]:
    return _METRICS.snapshot()


def reset_rate_limit_metrics() -> None:
    _METRICS.reset()


def _is_trusted_proxy(client_ip: str) -> bool:
    if not settings.RATE_LIMIT_TRUST_PROXY_HEADERS:
        return False

    if not settings.RATE_LIMIT_TRUSTED_PROXIES:
        return False

    try:
        parsed_client_ip = ip_address(client_ip)
    except ValueError:
        return False

    for proxy in settings.RATE_LIMIT_TRUSTED_PROXIES:
        try:
            trusted_network = ip_network(proxy, strict=False)
        except ValueError:
            continue
        if parsed_client_ip in trusted_network:
            return True
    return False


def _extract_forwarded_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        for hop in forwarded_for.split(","):
            candidate = hop.strip()
            if not candidate:
                continue
            try:
                ip_address(candidate)
            except ValueError:
                continue
            return candidate

    real_ip = request.headers.get("x-real-ip", "").strip()
    if not real_ip:
        return None

    try:
        ip_address(real_ip)
    except ValueError:
        return None
    return real_ip


def client_ip_identifier(request: Request) -> str:
    client_ip = "unknown"
    if request.client and request.client.host:
        client_ip = request.client.host

    if client_ip != "unknown" and _is_trusted_proxy(client_ip):
        forwarded_ip = _extract_forwarded_ip(request)
        if forwarded_ip:
            return forwarded_ip

    return client_ip


async def _async_client_ip_identifier(request: Request) -> str:
    return client_ip_identifier(request)


async def init_rate_limiter() -> None:
    _STATE.ready = False

    if not _is_redis_backend_enabled():
        return

    if not rate_limit_dependencies_available():
        logger.error(
            "Rate limiting enabled but dependencies are missing. "
            "Install 'fastapi-limiter' and 'redis'."
        )
        return

    try:
        redis_client = redis_asyncio.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        await _init_fastapi_limiter(redis_client)
        _STATE.redis_client = redis_client
        _STATE.ready = True
        logger.info(
            "Redis rate limiter initialized backend=%s prefix=%s",
            settings.RATE_LIMIT_BACKEND,
            settings.RATE_LIMIT_PREFIX,
        )
    except Exception:
        _STATE.redis_client = None
        _STATE.ready = False
        logger.exception("Failed to initialize Redis rate limiter")


async def shutdown_rate_limiter() -> None:
    redis_client = _STATE.redis_client

    if FastAPILimiter is not None and hasattr(FastAPILimiter, "close"):
        try:
            await FastAPILimiter.close()
        except Exception:
            logger.exception("Failed to close FastAPILimiter")

    if redis_client is not None:
        try:
            close_method = getattr(redis_client, "aclose", None)
            if close_method is not None:
                await close_method()
            else:
                await redis_client.close()
        except Exception:
            logger.exception("Failed to close Redis rate limiter client")

    _STATE.redis_client = None
    _STATE.ready = False


def is_rate_limiter_ready() -> bool:
    if not _is_redis_backend_enabled():
        return True
    return _STATE.ready


def _raise_unavailable(endpoint: str, request: Request) -> None:
    _record_metric(endpoint, "redis_unavailable")

    if settings.RATE_LIMIT_FAIL_OPEN:
        logger.warning(
            "Rate limiter unavailable; allowing request endpoint=%s client_ip=%s mode=fail_open",
            endpoint,
            client_ip_identifier(request),
        )
        _record_metric(endpoint, "allowed")
        return

    logger.error(
        "Rate limiter unavailable; rejecting request endpoint=%s client_ip=%s mode=fail_closed",
        endpoint,
        client_ip_identifier(request),
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Rate limiting service unavailable",
    )


async def _enforce_endpoint_rate_limit(
    *,
    endpoint: str,
    times: int,
    seconds: int,
    request: Request,
    response: Response,
) -> None:
    if not _is_redis_backend_enabled():
        return

    if times <= 0 or seconds <= 0:
        logger.warning(
            "Skipping misconfigured rate limit endpoint=%s times=%s seconds=%s",
            endpoint,
            times,
            seconds,
        )
        return

    if RateLimiter is None:
        _raise_unavailable(endpoint, request)
        return

    if not is_rate_limiter_ready():
        await init_rate_limiter()
    if not is_rate_limiter_ready():
        _raise_unavailable(endpoint, request)
        return

    limiter = _build_rate_limiter(times, seconds)

    try:
        await _invoke_rate_limiter(limiter, request, response)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            _record_metric(endpoint, "limited")
            logger.warning(
                "Rate limit blocked endpoint=%s client_ip=%s times=%s seconds=%s",
                endpoint,
                client_ip_identifier(request),
                times,
                seconds,
            )
        raise
    except Exception:
        _STATE.ready = False
        logger.exception(
            "Redis rate limiter error endpoint=%s client_ip=%s",
            endpoint,
            client_ip_identifier(request),
        )
        _raise_unavailable(endpoint, request)
    else:
        _record_metric(endpoint, "allowed")


def _build_rate_limit_dependency(
    *,
    endpoint: str,
    times_setting: str,
    seconds_setting: str,
) -> RateLimitDependency:
    async def dependency(request: Request, response: Response) -> None:
        await _enforce_endpoint_rate_limit(
            endpoint=endpoint,
            times=int(getattr(settings, times_setting)),
            seconds=int(getattr(settings, seconds_setting)),
            request=request,
            response=response,
        )

    dependency.__name__ = f"{endpoint.replace('.', '_')}_rate_limit_dependency"
    return dependency


login_rate_limit_dependency = _build_rate_limit_dependency(
    endpoint="auth.login",
    times_setting="RATE_LIMIT_LOGIN_TIMES",
    seconds_setting="RATE_LIMIT_LOGIN_SECONDS",
)

register_rate_limit_dependency = _build_rate_limit_dependency(
    endpoint="auth.register",
    times_setting="RATE_LIMIT_REGISTER_TIMES",
    seconds_setting="RATE_LIMIT_REGISTER_SECONDS",
)

refresh_rate_limit_dependency = _build_rate_limit_dependency(
    endpoint="auth.refresh",
    times_setting="RATE_LIMIT_REFRESH_TIMES",
    seconds_setting="RATE_LIMIT_REFRESH_SECONDS",
)

password_reset_route_rate_limit_dependency = _build_rate_limit_dependency(
    endpoint="auth.password_reset.request",
    times_setting="RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_TIMES",
    seconds_setting="RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_SECONDS",
)


__all__ = [
    "client_ip_identifier",
    "get_rate_limit_metrics_snapshot",
    "init_rate_limiter",
    "is_rate_limiter_ready",
    "login_rate_limit_dependency",
    "password_reset_route_rate_limit_dependency",
    "rate_limit_dependencies_available",
    "refresh_rate_limit_dependency",
    "register_rate_limit_dependency",
    "reset_rate_limit_metrics",
    "shutdown_rate_limiter",
]
