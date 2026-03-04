#!/usr/bin/env bash
set -euo pipefail

# Verify webhook idempotency without DB access.
# Sends the same entry_id twice and asserts second response is idempotent replay.
#
# Usage:
#   ./scripts/check_wpforms_idempotency.sh "<webhook_url>" "<hmac_secret>" [entry_id]
#
# Example:
#   ./scripts/check_wpforms_idempotency.sh \
#     "https://abcd.ngrok-free.app/api/v1/webhooks/wpforms/survey" \
#     "your_hmac_secret" \
#     "idem-001"

if [[ "${1:-}" == "" || "${2:-}" == "" ]]; then
  echo "Usage: $0 <webhook_url> <hmac_secret> [entry_id]"
  exit 1
fi

WEBHOOK_URL="$1"
HMAC_SECRET="$2"
ENTRY_ID="${3:-idem-$(date +%s)}"
TIMESTAMP="$(date +%s)"

read -r -d '' PAYLOAD <<EOF || true
{
  "entry_id": "${ENTRY_ID}",
  "form_id": "idempotency-check",
  "fields": [
    {"name":"What is your First & Last Name?:","value":"Idem\nCheck"},
    {"name":"What state are you located in?:","value":"Florida"},
    {"name":"Please provide your Mobile Phone Number::","value":"3055551234"},
    {"name":"Please Enter Your Zip Code:","value":"33415"}
  ]
}
EOF

SIGNING_INPUT="${TIMESTAMP}.${PAYLOAD}"
SIGNATURE="$(
  printf "%s" "${SIGNING_INPUT}" \
    | openssl dgst -sha256 -hmac "${HMAC_SECRET}" -binary \
    | xxd -p -c 256
)"

request_once() {
  local out_file status_code body
  out_file="$(mktemp)"
  status_code="$(
    curl -sS -o "${out_file}" -w "%{http_code}" -X POST "${WEBHOOK_URL}" \
      -H "Content-Type: application/json" \
      -H "X-Webhook-Timestamp: ${TIMESTAMP}" \
      -H "X-Webhook-Signature: ${SIGNATURE}" \
      --data "${PAYLOAD}"
  )"
  body="$(cat "${out_file}")"
  rm -f "${out_file}"
  printf "%s\n%s\n" "${status_code}" "${body}"
}

echo "Entry ID: ${ENTRY_ID}"
echo "Posting first request..."
first_result="$(request_once)"
first_status="$(printf "%s" "${first_result}" | sed -n '1p')"
first_body="$(printf "%s" "${first_result}" | sed -n '2,$p')"
echo "HTTP ${first_status}"
echo "${first_body}"
echo

echo "Posting second request with same entry_id..."
second_result="$(request_once)"
second_status="$(printf "%s" "${second_result}" | sed -n '1p')"
second_body="$(printf "%s" "${second_result}" | sed -n '2,$p')"
echo "HTTP ${second_status}"
echo "${second_body}"
echo

python - "${first_status}" "${first_body}" "${second_status}" "${second_body}" <<'PY'
import json
import sys

first_status = int(sys.argv[1])
first_body_raw = sys.argv[2]
second_status = int(sys.argv[3])
second_body_raw = sys.argv[4]

if first_status != 200:
    print("FAIL: first request did not return HTTP 200")
    sys.exit(1)
if second_status != 200:
    print("FAIL: second request did not return HTTP 200")
    sys.exit(1)

try:
    first = json.loads(first_body_raw)
    second = json.loads(second_body_raw)
except Exception:
    print("FAIL: response body is not valid JSON")
    sys.exit(1)

if bool(first.get("idempotent_replay")):
    print("FAIL: first request unexpectedly reported idempotent replay")
    sys.exit(1)

if not bool(second.get("idempotent_replay")):
    print("FAIL: second request did not report idempotent replay=true")
    sys.exit(1)

print("PASS: idempotency verified (second request is replay)")
PY
