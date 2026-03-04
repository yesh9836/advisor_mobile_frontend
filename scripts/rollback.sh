#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

target_release=""
db_backup_path=""
yes_restore="false"
skip_smoke="false"
timeout_seconds=240

usage() {
  cat <<EOF
Usage: $(basename "$0") [--to-release <release_id>] [--db-backup <path.sql.gz|path.sql>] [--yes] [--skip-smoke] [--timeout-seconds <n>]

Rolls back application code to a previous recorded release and redeploys containers.
If --db-backup is provided, also restores MySQL from that dump.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --to-release)
      shift
      [ "$#" -gt 0 ] || die "--to-release requires a value"
      target_release="$1"
      ;;
    --db-backup)
      shift
      [ "$#" -gt 0 ] || die "--db-backup requires a value"
      db_backup_path="$1"
      ;;
    --yes)
      yes_restore="true"
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
      usage
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
require_cmd ls
require_cmd sort
require_file "${ENV_FILE}"
require_file "${COMPOSE_FILE}"

mkdir -p "${RELEASE_ROOT}"

mapfile -t releases < <(ls -1 "${RELEASE_ROOT}" 2>/dev/null | grep -E '^[0-9]{8}-[0-9]{6}$' | sort || true)
count="${#releases[@]}"
[ "${count}" -gt 0 ] || die "No releases found in ${RELEASE_ROOT}. Run deploy.sh first."

if [ -z "${target_release}" ]; then
  [ "${count}" -ge 2 ] || die "Only one release exists. Pass --to-release explicitly."
  target_release="${releases[$((count - 2))]}"
fi

target_dir="${RELEASE_ROOT}/${target_release}"
target_meta="${target_dir}/release.env"
[ -d "${target_dir}" ] || die "Release directory not found: ${target_dir}"
require_file "${target_meta}"

# shellcheck disable=SC1090
source "${target_meta}"

[ -n "${GIT_SHA:-}" ] || die "Release metadata missing GIT_SHA in ${target_meta}"
git -C "${ROOT_DIR}" cat-file -e "${GIT_SHA}^{commit}" >/dev/null 2>&1 || die "Git commit not found locally: ${GIT_SHA}"

if [ -n "$(git -C "${ROOT_DIR}" status --porcelain)" ]; then
  die "Working tree is not clean. Commit/stash local changes before rollback."
fi

if [ -n "${db_backup_path}" ]; then
  [ -f "${db_backup_path}" ] || die "DB backup file not found: ${db_backup_path}"
  if [ "${yes_restore}" != "true" ]; then
    printf 'DB restore will overwrite current database. Continue? [y/N]: '
    read -r confirm
    case "${confirm}" in
      y|Y|yes|YES) ;;
      *) die "Rollback cancelled by user." ;;
    esac
  fi
fi

log "Checking out rollback commit ${GIT_SHA} from release ${target_release}"
git -C "${ROOT_DIR}" checkout --detach "${GIT_SHA}"

if [ -n "${db_backup_path}" ]; then
  log "Stopping app services before DB restore"
  compose stop backend frontend stripe-worker notification-worker retention-worker || true
  compose up -d mysql redis

  log "Restoring DB from ${db_backup_path}"
  if [[ "${db_backup_path}" == *.gz ]]; then
    gunzip -c "${db_backup_path}" | compose exec -T mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
  else
    cat "${db_backup_path}" | compose exec -T mysql sh -lc 'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
  fi
fi

log "Rebuilding and starting services for rollback release ${target_release}"
compose up -d --build

backend_port="$(trim_quotes "$(get_env_value BACKEND_PORT)")"
[ -n "${backend_port}" ] || backend_port="8000"
ready_url="http://127.0.0.1:${backend_port}/health/ready"

log "Waiting for readiness at ${ready_url}"
if ! wait_for_ready "${ready_url}" "${timeout_seconds}" 5; then
  compose logs --since=15m backend stripe-worker notification-worker retention-worker || true
  die "Rollback readiness did not become healthy within ${timeout_seconds}s."
fi

if [ "${skip_smoke}" != "true" ]; then
  "${SCRIPT_DIR}/smoke.sh"
fi

log "Rollback succeeded."
log "Active commit: ${GIT_SHA}"
if [ -n "${db_backup_path}" ]; then
  log "DB restore applied from: ${db_backup_path}"
fi
