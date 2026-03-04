#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

base_url=""
local_only="false"
timeout_seconds=20

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url)
      shift
      [ "$#" -gt 0 ] || die "--base-url requires a value"
      base_url="$1"
      ;;
    --local-only)
      local_only="true"
      ;;
    --timeout-seconds)
      shift
      [ "$#" -gt 0 ] || die "--timeout-seconds requires a value"
      timeout_seconds="$1"
      ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [--base-url <https://app.domain.com>] [--local-only] [--timeout-seconds <n>]

Runs post-deploy smoke checks against backend and public app endpoints.
EOF
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
  shift
done

require_file "${ENV_FILE}"
require_cmd curl
require_cmd grep

backend_port="$(trim_quotes "$(get_env_value BACKEND_PORT)")"
[ -n "${backend_port}" ] || backend_port="8000"
backend_url="http://127.0.0.1:${backend_port}"

if [ -z "${base_url}" ] && [ "${local_only}" != "true" ]; then
  base_url="$(trim_quotes "$(get_env_value FRONTEND_URL)")"
fi

log "Running smoke checks..."

curl -fsS --max-time "${timeout_seconds}" "${backend_url}/health/live" >/dev/null
ready_payload="$(curl -fsS --max-time "${timeout_seconds}" "${backend_url}/health/ready")"
printf '%s' "${ready_payload}" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"healthy"' \
  || die "Local backend readiness is not healthy."

auth_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${timeout_seconds}" "${backend_url}/api/v1/auth/me" || true)"
case "${auth_code}" in
  200|401|403) ;;
  *) die "Unexpected auth/me HTTP status on local backend: ${auth_code}" ;;
esac

if [ "${local_only}" = "true" ]; then
  log "Smoke checks passed (local-only mode)."
  exit 0
fi

[ -n "${base_url}" ] || die "Missing base URL. Provide --base-url or set FRONTEND_URL in ${ENV_FILE}."

login_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${timeout_seconds}" "${base_url%/}/login" || true)"
case "${login_code}" in
  200|301|302|304) ;;
  *) die "Unexpected ${base_url%/}/login HTTP status: ${login_code}" ;;
esac

public_ready="$(curl -fsS --max-time "${timeout_seconds}" "${base_url%/}/health/ready")"
printf '%s' "${public_ready}" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"healthy"' \
  || die "Public readiness is not healthy at ${base_url%/}/health/ready."

public_auth_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "${timeout_seconds}" "${base_url%/}/api/v1/auth/me" || true)"
case "${public_auth_code}" in
  200|401|403) ;;
  *) die "Unexpected public auth/me HTTP status: ${public_auth_code}" ;;
esac

log "Smoke checks passed."
