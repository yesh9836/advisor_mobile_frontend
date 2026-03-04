#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

MIN_FREE_GB="${MIN_FREE_GB:-5}"

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  cat <<EOF
Usage: $(basename "$0")

Runs production preflight checks for env, Docker, compose config, and disk capacity.
EOF
  exit 0
fi

log "Running preflight checks..."
require_file "${ENV_FILE}"
require_file "${COMPOSE_FILE}"

require_cmd docker
require_cmd curl
require_cmd awk
require_cmd sed
require_cmd grep
require_cmd df

docker info >/dev/null 2>&1 || die "Docker daemon is unavailable. Start Docker first."
docker compose version >/dev/null 2>&1 || die "docker compose plugin is unavailable."

required_keys=(
  APP_ENV
  SECRET_KEY
  DB_NAME
  DB_USER
  DB_PASSWORD
  MYSQL_ROOT_PASSWORD
  VITE_API_BASE_URL
  FRONTEND_URL
  CORS_ORIGINS
)

for key in "${required_keys[@]}"; do
  has_env_key "${key}" || die "Missing required key in ${ENV_FILE}: ${key}"
  value="$(trim_quotes "$(get_env_value "${key}")")"
  [ -n "${value}" ] || die "Required key is empty in ${ENV_FILE}: ${key}"
done

secret_key="$(trim_quotes "$(get_env_value SECRET_KEY)")"
[ "${#secret_key}" -ge 32 ] || die "SECRET_KEY must be at least 32 characters."

validate_https_non_loopback_url "VITE_API_BASE_URL" "$(get_env_value VITE_API_BASE_URL)"
validate_https_non_loopback_url "FRONTEND_URL" "$(get_env_value FRONTEND_URL)"

app_env="$(trim_quotes "$(get_env_value APP_ENV)")"
if [ "${app_env}" != "production" ]; then
  warn "APP_ENV=${app_env}. Recommended: APP_ENV=production for go-live."
fi

sentry_backend_dsn="$(trim_quotes "$(get_env_value SENTRY_DSN)")"
sentry_frontend_dsn="$(trim_quotes "$(get_env_value VITE_SENTRY_DSN)")"
sentry_auth_token="$(trim_quotes "$(get_env_value SENTRY_AUTH_TOKEN)")"
sentry_org="$(trim_quotes "$(get_env_value SENTRY_ORG)")"
sentry_project="$(trim_quotes "$(get_env_value SENTRY_PROJECT)")"
sentry_backend_release="$(trim_quotes "$(get_env_value SENTRY_RELEASE)")"
sentry_frontend_release="$(trim_quotes "$(get_env_value VITE_SENTRY_RELEASE)")"

if [ -n "${sentry_backend_dsn}" ] || [ -n "${sentry_frontend_dsn}" ] || [ -n "${sentry_auth_token}" ] || [ -n "${sentry_org}" ] || [ -n "${sentry_project}" ]; then
  [ -n "${sentry_backend_dsn}" ] || die "Sentry is partially configured: SENTRY_DSN is missing."
  [ -n "${sentry_frontend_dsn}" ] || die "Sentry is partially configured: VITE_SENTRY_DSN is missing."

  if [ -n "${sentry_auth_token}" ] || [ -n "${sentry_org}" ] || [ -n "${sentry_project}" ]; then
    [ -n "${sentry_auth_token}" ] || die "Sentry sourcemap upload is partially configured: SENTRY_AUTH_TOKEN is missing."
    [ -n "${sentry_org}" ] || die "Sentry sourcemap upload is partially configured: SENTRY_ORG is missing."
    [ -n "${sentry_project}" ] || die "Sentry sourcemap upload is partially configured: SENTRY_PROJECT is missing."
  else
    warn "Sentry sourcemap upload credentials are not configured. Frontend source maps will not upload during deploy builds."
  fi
else
  if [ "${app_env}" = "production" ]; then
    warn "Sentry DSNs are not configured for production. Runtime error tracking will be disabled."
  fi
fi

if [ -n "${sentry_backend_release}" ] && [ -n "${sentry_frontend_release}" ] && [ "${sentry_backend_release}" != "${sentry_frontend_release}" ]; then
  warn "SENTRY_RELEASE and VITE_SENTRY_RELEASE differ in ${ENV_FILE}; deploy script will enforce one shared release value."
fi

free_kb="$(df -Pk "${ROOT_DIR}" | awk 'NR==2 {print $4}')"
free_gb="$((free_kb / 1024 / 1024))"
if [ "${free_gb}" -lt "${MIN_FREE_GB}" ]; then
  die "Low disk space: ${free_gb}GB free, need at least ${MIN_FREE_GB}GB."
fi

if ! compose config -q; then
  die "docker compose config validation failed."
fi

warn_keys=(
  STRIPE_SECRET_KEY
  STRIPE_PUBLISHABLE_KEY
  STRIPE_WEBHOOK_SECRET
)
for key in "${warn_keys[@]}"; do
  if has_env_key "${key}"; then
    value="$(trim_quotes "$(get_env_value "${key}")")"
    if [ -z "${value}" ]; then
      warn "${key} is empty. Stripe flows may fail in production."
    fi
  fi
done

log "Preflight checks passed."
