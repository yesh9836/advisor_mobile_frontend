#!/usr/bin/env bash
set -euo pipefail

# One-command end-to-end test:
# 1) Send signed WPForms-style webhook payload.
# 2) Verify inserted event/lead by entry_id.
#
# Usage:
#   ./scripts/run_wpforms_e2e_verify.sh "<webhook_url>" "<hmac_secret>" [entry_id]
#
# Example:
#   ./scripts/run_wpforms_e2e_verify.sh \
#     "https://abcd.ngrok-free.app/api/v1/webhooks/wpforms/survey" \
#     "your_hmac_secret" \
#     "entry-9100"

if [[ "${1:-}" == "" || "${2:-}" == "" ]]; then
  echo "Usage: $0 <webhook_url> <hmac_secret> [entry_id]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

WEBHOOK_URL="$1"
HMAC_SECRET="$2"
ENTRY_ID="${3:-e2e-$(date +%s)}"

echo "Note: DB verification reads the database configured in backend/.env on this machine."
echo "If WEBHOOK_URL points to another environment/database, 'found=false' is expected locally."
echo

echo "Sending signed webhook..."
"${SCRIPT_DIR}/send_wpforms_test_webhook.sh" "${WEBHOOK_URL}" "${HMAC_SECRET}" "${ENTRY_ID}"
echo

echo "Verifying DB insertion for entry_id=${ENTRY_ID}..."
attempt=1
max_attempts=5
while (( attempt <= max_attempts )); do
  if python "${SCRIPT_DIR}/verify_wpforms_ingest.py" --entry-id "${ENTRY_ID}" --pretty; then
    echo
    echo "Verification succeeded."
    exit 0
  fi

  if (( attempt == max_attempts )); then
    echo
    echo "Verification failed after ${max_attempts} attempts."
    exit 1
  fi

  echo "Not found yet (attempt ${attempt}/${max_attempts}); retrying in 1s..."
  sleep 1
  ((attempt++))
done

cd "${BACKEND_DIR}" >/dev/null 2>&1 || true
