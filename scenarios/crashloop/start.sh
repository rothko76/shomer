#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/../lib.sh"
require_kind_context "${1:-}"

"${KUBECTL[@]}" apply -f "$DIR/scenario.yaml"
echo "Scenario started: crashloop. CrashLoopBackOff appears after ~1 min of restarts."
