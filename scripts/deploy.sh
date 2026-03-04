#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

skip_backup="false"
skip_build="false"
skip_smoke="false"
timeout_seconds=240

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-backup)
      skip_backup="true"
      ;;
    --skip-build)
      skip_build="true"
      ;;
    --skip-smoke)
      skip_smoke="true"
      ;;
    --timeout-seconds)
      shift
      [ "$#" -gt 0 ] || die "--timeout-seconds requires a value"
      timeout_seconds="$1"
      ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [--skip-backup] [--skip-build] [--skip-smoke] [--timeout-seconds <n>]

Runs preflight, backup, compose deploy, readiness wait, and smoke checks.
EOF
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
  shift
done

require_cmd git
require_cmd docker
require_cmd awk
require_cmd tee

mkdir -p "${RELEASE_ROOT}"

log "Step 1/5: Preflight"
"${SCRIPT_DIR}/preflight.sh"

backup_id="skipped"
if [ "${skip_backup}" != "true" ]; then
  log "Step 2/5: Backup"
  backup_output="$("${SCRIPT_DIR}/backup.sh" --label predeploy | tee /dev/stderr)"
  backup_id="$(printf '%s\n' "${backup_output}" | awk -F= '/^BACKUP_ID=/ {print $2}' | tail -n1)"
  [ -n "${backup_id}" ] || die "Backup completed but BACKUP_ID was not captured."
else
  log "Step 2/5: Backup skipped"
fi

release_id="$(date -u +%Y%m%d-%H%M%S)"
release_dir="${RELEASE_ROOT}/${release_id}"
mkdir -p "${release_dir}"

git_sha="$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || printf 'unknown')"
branch_name="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || printf 'unknown')"
app_env="$(trim_quotes "$(get_env_value APP_ENV)")"
[ -n "${app_env}" ] || app_env="staging"

configured_sentry_release="$(trim_quotes "$(get_env_value SENTRY_RELEASE)")"
if [ -n "${SENTRY_RELEASE:-}" ]; then
  sentry_release="$(trim_quotes "${SENTRY_RELEASE}")"
elif [ -n "${configured_sentry_release}" ]; then
  sentry_release="${configured_sentry_release}"
else
  sentry_release="${release_id}"
fi
export SENTRY_RELEASE="${sentry_release}"
export VITE_SENTRY_RELEASE="${sentry_release}"

if [ -z "${SENTRY_ENVIRONMENT:-}" ]; then
  export SENTRY_ENVIRONMENT="${app_env}"
fi
if [ -z "${VITE_SENTRY_ENVIRONMENT:-}" ]; then
  export VITE_SENTRY_ENVIRONMENT="${app_env}"
fi

log "Step 3/5: Deploying release ${release_id}"
log "Using Sentry release ${SENTRY_RELEASE} (environment ${SENTRY_ENVIRONMENT})."
if [ "${skip_build}" = "true" ]; then
  compose up -d
else
  compose up -d --build
fi

compose config > "${release_dir}/compose.resolved.yml"
cat > "${release_dir}/release.env" <<EOF
RELEASE_ID=${release_id}
CREATED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
GIT_SHA=${git_sha}
BRANCH=${branch_name}
BACKUP_ID=${backup_id}
SENTRY_RELEASE=${SENTRY_RELEASE}
SENTRY_ENVIRONMENT=${SENTRY_ENVIRONMENT}
VITE_SENTRY_RELEASE=${VITE_SENTRY_RELEASE}
VITE_SENTRY_ENVIRONMENT=${VITE_SENTRY_ENVIRONMENT}
EOF

ln -sfn "${release_dir}" "${RELEASE_ROOT}/current"
printf '%s|%s|%s|%s\n' "${release_id}" "${git_sha}" "${branch_name}" "${backup_id}" >> "${RELEASE_ROOT}/history.log"

backend_port="$(trim_quotes "$(get_env_value BACKEND_PORT)")"
[ -n "${backend_port}" ] || backend_port="8000"
ready_url="http://127.0.0.1:${backend_port}/health/ready"

log "Step 4/5: Waiting for readiness at ${ready_url}"
if ! wait_for_ready "${ready_url}" "${timeout_seconds}" 5; then
  compose logs --since=15m backend stripe-worker notification-worker retention-worker || true
  die "Readiness did not become healthy within ${timeout_seconds}s."
fi

if [ "${skip_smoke}" != "true" ]; then
  log "Step 5/5: Smoke checks"
  "${SCRIPT_DIR}/smoke.sh"
else
  log "Step 5/5: Smoke checks skipped"
fi

log "Deploy succeeded."
log "Release: ${release_id}"
log "Git SHA: ${git_sha}"
log "Backup: ${backup_id}"
log "Rollback command: ${SCRIPT_DIR}/rollback.sh"
