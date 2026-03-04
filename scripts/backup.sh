#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

label="manual"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --label)
      shift
      [ "$#" -gt 0 ] || die "--label requires a value"
      label="$1"
      ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [--label <name>]

Creates timestamped MySQL and uploads backups.
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
require_file "${COMPOSE_FILE}"
require_cmd docker
require_cmd gzip
require_cmd tar
require_cmd git

mkdir -p "${BACKUP_ROOT}/db" "${BACKUP_ROOT}/uploads" "${BACKUP_ROOT}/meta"

timestamp="$(date -u +%Y%m%d-%H%M%S)"
safe_label="$(printf '%s' "${label}" | tr -cd '[:alnum:]_-')"
backup_id="${timestamp}-${safe_label}"

db_path="${BACKUP_ROOT}/db/${backup_id}.sql.gz"
uploads_path="${BACKUP_ROOT}/uploads/${backup_id}-uploads.tgz"
meta_path="${BACKUP_ROOT}/meta/${backup_id}.txt"

log "Preparing backup ${backup_id}..."

service_running mysql || die "mysql service is not running. Start stack before backup."
service_running backend || die "backend service is not running. Start stack before backup."

log "Backing up MySQL to ${db_path}"
compose exec -T mysql sh -lc \
  'mysqldump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' \
  | gzip -c > "${db_path}"

log "Backing up uploads volume to ${uploads_path}"
compose exec -T backend sh -lc \
  'mkdir -p /app/uploads && tar czf - -C /app/uploads .' \
  > "${uploads_path}"

git_sha="$(git -C "${ROOT_DIR}" rev-parse HEAD 2>/dev/null || printf 'unknown')"

cat > "${meta_path}" <<EOF
backup_id=${backup_id}
created_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
git_sha=${git_sha}
db_path=${db_path}
uploads_path=${uploads_path}
env_file=${ENV_FILE}
compose_file=${COMPOSE_FILE}
EOF

ln -sfn "${meta_path}" "${BACKUP_ROOT}/meta/latest.txt"

log "Backup completed."
printf 'BACKUP_ID=%s\n' "${backup_id}"
printf 'DB_BACKUP=%s\n' "${db_path}"
printf 'UPLOADS_BACKUP=%s\n' "${uploads_path}"
