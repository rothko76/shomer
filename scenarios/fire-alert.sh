#!/usr/bin/env bash
# Send a scenario's Alertmanager payload to a locally running agent.
# Usage: ./scenarios/fire-alert.sh <scenario> [url]
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIO="${1:?usage: fire-alert.sh <scenario> [url]}"
URL="${2:-http://localhost:8000/webhook/alertmanager}"
TOKEN="${SHOMER_WEBHOOK_TOKEN:-$(sed -n 's/^SHOMER_WEBHOOK_TOKEN=//p' "$DIR/../app/.env" 2>/dev/null || true)}"

# A fresh fingerprint each time so the agent's dedupe window doesn't swallow re-runs.
payload="$(sed "s/\"fingerprint\": \"\([^\"]*\)\"/\"fingerprint\": \"\1-$(date +%s)\"/" "$DIR/$SCENARIO/alert.json")"
curl -sS -X POST "$URL" -H 'content-type: application/json' \
  ${TOKEN:+-H "Authorization: Bearer $TOKEN"} -d "$payload"
echo
