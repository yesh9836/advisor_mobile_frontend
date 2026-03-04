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
- Sentry monitoring:
  - Backend/API and worker scripts initialize Sentry when `SENTRY_DSN` is set.
  - Frontend initializes Sentry when `VITE_SENTRY_DSN` is set.
  - Source-map uploads are optional and run only when all of `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`, and `VITE_SENTRY_RELEASE` are provided at build time.
  - Deploy script enforces one shared release value for backend and frontend (`SENTRY_RELEASE` and `VITE_SENTRY_RELEASE`).

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

## Docker Deployment

This repository now includes:

- `backend/Dockerfile` for API/workers/migrations image.
- `frontend/Dockerfile` for a production frontend image served by Nginx.
- `docker-compose.yml` for MySQL, Redis, API, Stripe worker, notification worker, retention worker, and frontend.

Quick start:

1. Copy env template:
   - `cp .env.docker.example .env.docker`
2. Set required values in `.env.docker` (at minimum: `VITE_API_BASE_URL`, DB credentials, `SECRET_KEY`).
3. Build and start:
   - `docker compose --env-file .env.docker up -d --build`
4. Open the app:
   - `http://localhost:${FRONTEND_PORT:-8080}`

Notes:

- Frontend production build enforces absolute HTTPS `VITE_API_BASE_URL` and disallows loopback hosts.
- `migrate` runs `alembic upgrade head` before API/workers start.
- Uploaded files persist in Docker volume `uploads_data`.

### Operational scripts (VPS)

For first-time production deployment on a VPS, use:

1. Preflight checks:
   - `./scripts/preflight.sh`
2. Manual backup:
   - `./scripts/backup.sh --label predeploy`
3. Deploy:
   - `./scripts/deploy.sh`
4. Smoke checks only:
   - `./scripts/smoke.sh`
5. Roll back to previous release:
   - `./scripts/rollback.sh`
6. Roll back with DB restore:
   - `./scripts/rollback.sh --db-backup ./backups/db/<backup>.sql.gz --yes`

Details:

- Release metadata is stored in `releases/<timestamp>/release.env`.
- Backups are stored in `backups/db` and `backups/uploads`.
- `deploy.sh` runs preflight, backup, deploy, readiness wait, and smoke checks by default.

### Local test flow (recommended first pass)

Because frontend production build requires HTTPS/non-loopback API base URL, start by validating backend + workers in Docker, then run frontend in dev mode locally:

1. Start backend stack:
   - `docker compose --env-file .env.docker up -d --build mysql redis migrate backend stripe-worker notification-worker retention-worker`
2. Verify API health:
   - `curl http://localhost:8000/health/live`
   - `curl http://localhost:8000/health/ready`
3. Run frontend dev server from `frontend/`:
   - `VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev`
