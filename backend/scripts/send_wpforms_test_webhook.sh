#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/send_wpforms_test_webhook.sh "https://<ngrok>/api/v1/webhooks/wpforms/survey" "your_hmac_secret" [entry_id]
#
# Example:
#   ./scripts/send_wpforms_test_webhook.sh \
#     "https://abcd-12-34-56-78.ngrok-free.app/api/v1/webhooks/wpforms/survey" \
#     "super_secret" \
#     "entry-9001"

if [[ "${1:-}" == "" || "${2:-}" == "" ]]; then
  echo "Usage: $0 <webhook_url> <hmac_secret> [entry_id]"
  exit 1
fi

WEBHOOK_URL="$1"
HMAC_SECRET="$2"
ENTRY_ID="${3:-test-$(date +%s)}"
TIMESTAMP="$(date +%s)"

read -r -d '' PAYLOAD <<EOF || true
{
  "entry_id": "${ENTRY_ID}",
  "form_id": "shell-test",
  "fields": [
    {"name":"What is your First & Last Name?:","value":"Bernard\nFrazier"},
    {"name":"When would you like to retire?:","value":"5-9 Years"},
    {"name":"How confident are you in your current long-term financial plan?:","value":"Not confident"},
    {"name":"What activity is most important to you in retirement?:","value":"Working part-time"},
    {"name":"How would you characterize your overall health?:","value":"Fair"},
    {"name":"Are you planning on relocating for retirement?:","value":"No"},
    {"name":"Where do you expect the majority of your retirement income to come from?:","value":"Employer (Pensions)"},
    {"name":"How do you currently manage your money?:","value":"I work with a Financial Advisor"},
    {"name":"Which statement best describes you?:","value":"I prefer lower-risk investments that are typically safer and have steady returns"},
    {"name":"What is your main purpose for investing? (Check all that apply):","value":"Leaving a Legacy"},
    {"name":"How comfortable are you with investing?:","value":"Not comfortable at all"},
    {"name":"About what amount do you currently have saved for retirement?:","value":"\$250,000 - \$500,000"},
    {"name":"How quickly would you like to improve your long-term financial strategy?:","value":"Within the next year"},
    {"name":"What investment strategies are you currently using? (Check all that apply):","value":"Active Trading, Real Estate"},
    {"name":"Do you currently have a financial advisor?:","value":"Yes, but I'm considering switching advisors"},
    {"name":"Would you prefer your financial advisor to be located in your immediate area?:","value":"No, I am comfortable working by phone or video-conference"},
    {"name":"Please estimate your annual household income:","value":"\$150,000 - \$249,999"},
    {"name":"Please estimate your total investable assets:","value":"\$250,000 - \$999,999"},
    {"name":"Please estimate your current monthly savings:","value":"\$500 - \$999"},
    {"name":"Do you currently own an annuity?:","value":"No"},
    {"name":"Which follow-up method would you prefer?:","value":"Either a phone call or text"},
    {"name":"What state are you located in?:","value":"Florida"},
    {"name":"Please Enter Your Zip Code:","value":"33415"},
    {"name":"Please provide your Mobile Phone Number::","value":"3054959490"},
    {"name":"What is the best time of day to reach you?:","value":"AM on"},
    {"name":"Is there anything else you'd like us to know?:","value":""}
  ]
}
EOF

# Safety check: ensure payload entry_id matches the command argument.
PAYLOAD_ENTRY_ID="$(
  printf "%s" "${PAYLOAD}" \
    | sed -n 's/.*"entry_id":[[:space:]]*"\([^"]*\)".*/\1/p' \
    | head -n 1
)"
if [[ "${PAYLOAD_ENTRY_ID}" != "${ENTRY_ID}" ]]; then
  echo "ERROR: payload entry_id (${PAYLOAD_ENTRY_ID}) does not match ENTRY_ID arg (${ENTRY_ID})"
  echo "Do not hardcode entry_id inside the payload template."
  exit 1
fi

SIGNING_INPUT="${TIMESTAMP}.${PAYLOAD}"
SIGNATURE="$(
  printf "%s" "${SIGNING_INPUT}" \
    | openssl dgst -sha256 -hmac "${HMAC_SECRET}" -binary \
    | xxd -p -c 256
)"

echo "POST ${WEBHOOK_URL}"
echo "entry_id=${ENTRY_ID}"
echo "timestamp=${TIMESTAMP}"
echo "signature=${SIGNATURE}"
echo

curl -i -sS -X POST "${WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Timestamp: ${TIMESTAMP}" \
  -H "X-Webhook-Signature: ${SIGNATURE}" \
  --data "${PAYLOAD}"
