# Lead Management Platform

Production-oriented lead management for financial advisors. The application provides role-based authentication, license-gated lead access, one-time Stripe purchases, lead delivery, advisor goals, notifications, and administrative reporting.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, MySQL, and Redis
- Frontend: React 19, TypeScript, and Vite
- Payments: Stripe Checkout and signed webhooks
- Notifications: SMTP2GO email and Twilio SMS
- Runtime: Docker Compose with separate API, migration, worker, and frontend services
- Tests: pytest, Vitest, and Playwright

## Developer Quick Start

This is the recommended first-time setup. MySQL, Redis, migrations, and the API run in Docker; the frontend runs through Vite so it can use local HTTP safely.

### Prerequisites

- Docker with the Docker Compose plugin
- Node.js 22 and npm 10 or newer
- `nvm` is optional; the repository includes `.nvmrc`
- Python 3.12 is needed only when running the backend outside Docker

### 1. Create the Docker environment

From the repository root:

```bash
cp .env.docker.example .env.docker
```

For local development, set these values in `.env.docker`:

```dotenv
APP_ENV=development
SECRET_KEY=<random-32-plus-character-value>
FRONTEND_URL=http://localhost:5173
CORS_ORIGINS=["http://localhost:5173"]
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
```

Generate a suitable local secret with:

```bash
openssl rand -hex 32
```

Keep `.env.docker` private. It is ignored by Git and must never be committed.

### 2. Start the backend services

```bash
docker compose --env-file .env.docker up -d --build \
  mysql redis migrate backend stripe-worker notification-worker retention-worker
```

The `migrate` service runs `alembic upgrade head` before the API and workers start.

Verify the API:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Both endpoints should respond successfully; readiness reports the database and rate-limiter state.

### 3. Create demo accounts

Create or refresh one demo admin and one demo advisor after the backend is healthy:

```bash
docker compose --env-file .env.docker exec backend \
  python scripts/create_demo_users.py
```

Demo logins:

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin.demo@example.com` | `Password123!` |
| Advisor | `advisor.demo@example.com` | `Password123!` |

The script creates users only. Add licenses, packages, leads, purchases, goals, and delivery settings through the application workflows so development exercises the same behavior as real usage. Existing demo accounts are reactivated and their passwords are reset to the displayed values.

The script refuses to run when `APP_ENV=production`. Override its defaults with `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD`, `DEMO_ADVISOR_EMAIL`, `DEMO_ADVISOR_PASSWORD`, or the shared `DEMO_USER_PASSWORD` environment variable before recreating the backend container.

### 4. Start the frontend

In another terminal:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000/api/v1 npm run dev
```

If `nvm` is installed, run `nvm use` before `npm ci`; otherwise ensure the active Node version is 22.

Open [http://localhost:5173](http://localhost:5173) and sign in with either demo account.

### 5. Stop or reset the environment

Stop containers without deleting data:

```bash
docker compose --env-file .env.docker down
```

To completely reset the local database, Redis data, and uploads, use the following destructive command and then repeat the quick start:

```bash
docker compose --env-file .env.docker down -v
```

## Environment Configuration

`.env.docker.example` is the canonical Docker template. Keep secrets in `.env.docker` or in the secret manager used by the deployment platform.

### Core settings

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_ENV` | Yes | Use `development`, `staging`, or `production`. Production enables strict validation. |
| `SECRET_KEY` | Yes | Signs authentication tokens; production requires a strong non-default value of at least 32 characters. |
| `FRONTEND_URL` | Yes | Browser-facing application origin. Production requires an absolute HTTPS URL. |
| `CORS_ORIGINS` | Yes | JSON list of allowed frontend origins. Do not use wildcards with credentialed requests. |
| `AUTH_COOKIE_SECURE` | Yes | Use `false` only for local HTTP and `true` in production. |
| `AUTH_COOKIE_SAMESITE` | Yes | Normally `lax`; cross-site deployments require deliberate cookie and CSRF review. |
| `VITE_API_BASE_URL` | Frontend build | API base URL embedded into the frontend build. Production requires HTTPS and rejects loopback hosts. |
| `INITIAL_ADMIN_EMAIL` | First deployment | Email used by the one-time initial-admin command. |
| `INITIAL_ADMIN_PASSWORD` | First deployment | Strong initial password; the command never overwrites an existing admin password. |
| `INITIAL_ADMIN_NAME` | First deployment | Display name for the first administrator. |

### MySQL and Redis

| Variable | Required | Purpose |
| --- | --- | --- |
| `DB_NAME` | Yes | MySQL database name. |
| `DB_USER` | Yes | Application database user. |
| `DB_PASSWORD` | Yes | Application database password. |
| `MYSQL_ROOT_PASSWORD` | Yes | MySQL root password used to initialize the Docker volume. |
| `RATE_LIMIT_ENABLED` | Yes | Enables endpoint rate limiting. |
| `RATE_LIMIT_FAIL_OPEN` | Recommended | Keep `false` in production so protected routes fail closed if Redis is unavailable. |

Docker Compose supplies `DB_HOST=mysql` and `REDIS_URL=redis://redis:6379/0` to application services. Developers normally do not need to set them manually.

Data persists in these named volumes:

- `mysql_data`: application database
- `redis_data`: Redis persistence
- `uploads_data`: uploaded license and import files

### Stripe

For Stripe test or live flows, configure:

```dotenv
STRIPE_SECRET_KEY=sk_test_or_live_value
STRIPE_PUBLISHABLE_KEY=pk_test_or_live_value
STRIPE_WEBHOOK_SECRET=whsec_value
STRIPE_WEBHOOK_EXPECT_LIVEMODE=false
```

Use `STRIPE_WEBHOOK_EXPECT_LIVEMODE=false` for test mode and `true` for live mode. Register this public webhook endpoint in Stripe:

```text
https://your-domain.example/api/v1/webhooks/stripe
```

For local webhook testing with the Stripe CLI:

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

Copy the CLI-provided `whsec_...` value into `STRIPE_WEBHOOK_SECRET`, then recreate the backend and Stripe worker so they receive the updated environment:

```bash
docker compose --env-file .env.docker up -d --force-recreate backend stripe-worker
```

### SMTP2GO email

Email delivery is optional in development and staging. The current production configuration validator still requires an SMTP2GO host, port, and sender address even when notifications are disabled. To send email, configure the complete set:

```dotenv
NOTIFICATIONS_ENABLED=true
NOTIFICATION_EMAIL_ENABLED=true
NOTIFICATION_EMAIL_PROVIDER=smtp2go
SMTP_HOST=mail.smtp2go.com
SMTP_PORT=587
SMTP_USER=<smtp2go-user>
SMTP_PASSWORD=<smtp2go-password>
SMTP_FROM_EMAIL=<verified-sender@example.com>
NOTIFICATION_FROM_EMAIL=<verified-sender@example.com>
NOTIFICATION_FROM_NAME=Spectaculeads
```

The sender must be verified in SMTP2GO. Recreate `backend` and `notification-worker` after changing notification settings.

### Twilio SMS

SMS delivery is optional in development and staging. The current production configuration validator requires Twilio credentials and either a Messaging Service SID or sender number even when notifications are disabled. To send SMS, configure:

```dotenv
NOTIFICATIONS_ENABLED=true
NOTIFICATION_SMS_ENABLED=true
NOTIFICATION_SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=<account-sid>
TWILIO_AUTH_TOKEN=<auth-token>
TWILIO_MESSAGING_SERVICE_SID=<messaging-service-sid>
```

Use `TWILIO_FROM_NUMBER` instead of `TWILIO_MESSAGING_SERVICE_SID` only when the deployment is configured to send from a specific Twilio number. Trial accounts can send only to verified destinations.

### Sentry

Sentry is optional. Backend services use `SENTRY_DSN`; the frontend uses `VITE_SENTRY_DSN`. Frontend source-map upload additionally requires `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`, and a release value. The deploy script keeps backend and frontend release identifiers aligned.

## Production Docker Deployment

The frontend container serves HTTP through Nginx. Production requires TLS termination from a load balancer, ingress controller, CDN, or host-level reverse proxy in front of the Compose stack.

### Required production preparation

1. Point the application domain to the host and configure HTTPS.
2. Copy `.env.docker.example` to `.env.docker`.
3. Set `APP_ENV=production`.
4. Replace every `change_me` value and configure unique database credentials.
5. Set `FRONTEND_URL`, `CORS_ORIGINS`, and `VITE_API_BASE_URL` to the real HTTPS domain.
6. Set `AUTH_COOKIE_SECURE=true`.
7. Configure the initial-admin values before running the one-time admin command.
8. Configure Stripe secrets and webhook mode.
9. Configure SMTP2GO and Twilio values required by production validation; configure Sentry if error reporting is enabled.
10. Confirm the host has Docker, Compose, `curl`, and sufficient disk space.

Example origin settings for a single-domain deployment:

```dotenv
APP_ENV=production
FRONTEND_URL=https://app.example.com
CORS_ORIGINS=["https://app.example.com"]
VITE_API_BASE_URL=https://app.example.com/api/v1
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=lax
```

### Validate and deploy

```bash
./scripts/preflight.sh
./scripts/deploy.sh
```

`deploy.sh` runs preflight checks, creates a backup, builds and starts the stack, waits for readiness, and performs smoke checks. Migrations run through the one-shot `migrate` service before the API and workers start.

### Create the first production admin

After the API is healthy, create the first administrator from the values in `.env.docker`:

```bash
docker compose --env-file .env.docker exec backend \
  python scripts/create_initial_admin.py
```

The command creates one admin when the configured email does not exist. It refuses to promote an existing advisor and never changes an existing admin password. Run it again safely to confirm that the account already exists. After signing in, create packages and manage application data through the admin interface; advisors should use the normal registration and license workflows.

After the account is created, clear `INITIAL_ADMIN_PASSWORD` from `.env.docker` and recreate the application containers. The runtime does not require the bootstrap password, and it should not remain in the long-lived container environment.

### Production checks

```bash
curl https://app.example.com/health/live
curl https://app.example.com/health/ready
./scripts/smoke.sh --base-url https://app.example.com
```

Before go-live, confirm:

- HTTPS redirects and certificate renewal work.
- Database and upload backups complete successfully.
- A restore has been tested in a non-production environment.
- Stripe sends signed test events to the public webhook.
- The Stripe worker, notification worker, and retention worker remain healthy.
- Redis unavailability produces the intended fail-closed behavior.
- SMTP2GO and Twilio use verified senders and least-privilege credentials.
- Demo accounts and placeholder Stripe prices are absent.

## Common Commands

Run migrations manually:

```bash
docker compose --env-file .env.docker run --rm migrate
```

Inspect service state and logs:

```bash
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f backend
docker compose --env-file .env.docker logs -f stripe-worker notification-worker retention-worker
```

Create an on-demand backup:

```bash
./scripts/backup.sh --label manual
```

Run smoke checks against local backend services only:

```bash
./scripts/smoke.sh --local-only
```

Roll back the application release:

```bash
./scripts/rollback.sh
```

Restore a selected database backup while rolling back:

```bash
./scripts/rollback.sh --db-backup ./backups/db/<backup>.sql.gz --yes
```

Release metadata is stored under `releases/`; database and upload backups are stored under `backups/`. Both locations are ignored by Git.

## Running Tests

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
pytest
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run test:unit
npm run build
npx playwright install chromium
npm run test:e2e:mocked
```

CI runs backend functional linting and pytest, plus frontend ESLint, Vitest, a production build, and Playwright critical-flow tests.

## Troubleshooting

### The API is not ready

Inspect `mysql`, `redis`, `migrate`, and `backend` logs. The most common causes are invalid production environment values, database credentials that do not match an existing MySQL volume, or unavailable Redis.

```bash
docker compose --env-file .env.docker logs mysql redis migrate backend
```

### Login works in development but cookies disappear

For local HTTP, use `AUTH_COOKIE_SECURE=false`. For production, use HTTPS and `AUTH_COOKIE_SECURE=true`. Ensure `FRONTEND_URL` and `CORS_ORIGINS` exactly match the browser origin.

### Stripe checkout opens but cannot complete

Confirm that the package uses a real Stripe Price ID from the same Stripe account and mode as `STRIPE_SECRET_KEY`. Placeholder `price_fake_...` values cannot create checkout sessions.

### Notifications remain queued

Check that `NOTIFICATIONS_ENABLED=true`, the relevant email or SMS channel is enabled, provider credentials are present, and `notification-worker` is running.

## Architecture Notes

- `/health/live` is liveness-only; `/health/ready` checks fail-closed dependencies.
- Authentication uses secure cookie sessions, CSRF protection, and refresh-token rotation.
- Redis-backed auth rate limits fail closed by default.
- Stripe webhooks use an inbox/worker pipeline for durable processing and reconciliation.
- Uploaded files persist in `uploads_data` and must be backed up with the database.
- Proxy-derived client IP headers are trusted only when `RATE_LIMIT_TRUST_PROXY_HEADERS=true` and explicit trusted proxies are configured.
