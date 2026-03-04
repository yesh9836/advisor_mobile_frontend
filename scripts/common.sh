#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.docker}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.yml}"
BACKUP_ROOT="${BACKUP_ROOT:-${ROOT_DIR}/backups}"
RELEASE_ROOT="${RELEASE_ROOT:-${ROOT_DIR}/releases}"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

warn() {
  printf '[%s] WARNING: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

die() {
  printf '[%s] ERROR: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
  exit 1
}

require_cmd() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "Missing required command: ${cmd}"
}

require_file() {
  local path="$1"
  [ -f "${path}" ] || die "Required file not found: ${path}"
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

trim_quotes() {
  local value="$1"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "${value}"
}

has_env_key() {
  local key="$1"
  awk -F= -v wanted="${key}" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      current=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", current)
      if (current == wanted) {
        found=1
      }
    }
    END { exit(found ? 0 : 1) }
  ' "${ENV_FILE}"
}

get_env_value() {
  local key="$1"
  awk -F= -v wanted="${key}" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      current=$1
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", current)
      if (current == wanted) {
        sub(/^[^=]*=/, "", $0)
        value=$0
      }
    }
    END {
      if (value != "") {
        print value
      }
    }
  ' "${ENV_FILE}"
}

validate_https_non_loopback_url() {
  local label="$1"
  local raw="$2"
  local url host

  url="$(trim_quotes "${raw}")"
  [ -n "${url}" ] || die "${label} is empty"
  [[ "${url}" == https://* ]] || die "${label} must start with https:// (got: ${url})"

  host="$(printf '%s' "${url}" | sed -E 's#^https://([^/:]+).*$#\1#')"
  [ -n "${host}" ] || die "${label} has invalid host: ${url}"

  case "${host}" in
    localhost|127.0.0.1|0.0.0.0|::1)
      die "${label} cannot use loopback host: ${host}"
      ;;
    example.com|*.example.com)
      die "${label} cannot use placeholder host: ${host}"
      ;;
  esac
}

service_running() {
  local service="$1"
  compose exec -T "${service}" sh -lc 'true' >/dev/null 2>&1
}

wait_for_ready() {
  local url="$1"
  local timeout_seconds="${2:-240}"
  local interval_seconds="${3:-5}"
  local start now elapsed body

  start="$(date +%s)"
  while true; do
    set +e
    body="$(curl -fsS "${url}" 2>/dev/null)"
    rc=$?
    set -e
    if [ "${rc}" -eq 0 ] && printf '%s' "${body}" | grep -Eq '"status"[[:space:]]*:[[:space:]]*"healthy"'; then
      return 0
    fi

    now="$(date +%s)"
    elapsed="$((now - start))"
    if [ "${elapsed}" -ge "${timeout_seconds}" ]; then
      return 1
    fi
    sleep "${interval_seconds}"
  done
}
