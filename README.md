# lead-management-production

Production lead-management platform for financial advisors with one-time lead package purchases.

## Core Capabilities

- Role-based authentication (`advisor`, `admin`) with cookie sessions.
- One-time lead package checkout via Stripe.
- License-gated lead access and distribution by verified state licenses.
- Admin workflows for lead inventory, imports, user management, and analytics.
- Audit logging for privileged and operational actions.

## Current Architecture

### Backend

- FastAPI + SQLAlchemy (MySQL in production, SQLite for local tests).
- Cookie auth with CSRF protection and refresh-token rotation.
- Password hashing with Passlib + Argon2.
- Redis-backed endpoint rate limiting on auth paths.
- Stripe webhook ingestion with inbox/outbox worker patterns.

### Frontend

- React 19 + TypeScript + Vite.
- Axios API client with cookie credentials and refresh interceptor.
- Vitest unit/component tests plus Playwright browser e2e critical-flow tests.

## Production Behavior Notes

- Health endpoints:
  - `/health/live` is liveness-only.
  - `/health/ready` includes rate-limiter readiness and returns `503` when fail-closed dependencies are unavailable.
- Rate limiter:
  - Backend mode is Redis (`RATE_LIMIT_BACKEND=redis`).
  - Auth routes fail closed by default when limiter is unavailable (`RATE_LIMIT_FAIL_OPEN=false`).
  - Outage handling includes bounded retry backoff to avoid per-request Redis reconnect storms.
- Proxy safety:
  - Proxy-derived IP headers are trusted only when explicitly enabled.
  - Configure `RATE_LIMIT_TRUST_PROXY_HEADERS=true` with explicit `RATE_LIMIT_TRUSTED_PROXIES`.

## CI Quality Gates

- Backend (`.github/workflows/backend-pytest.yml`):
  - Functional lint gate (`flake8 --select=F,E9`),
  - pytest suite,
  - Redis-backed limiter integration tests.
- Frontend (`.github/workflows/frontend-ci.yml`):
  - ESLint,
  - Vitest suite,
  - production build,
  - Playwright e2e critical flows (auth cookies, CSRF, refresh, checkout return).
