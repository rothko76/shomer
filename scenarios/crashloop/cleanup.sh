#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/../lib.sh"
require_kind_context "${1:-}"

"${KUBECTL[@]}" delete -f "$DIR/scenario.yaml" --ignore-not-found=true
echo "Scenario cleaned: crashloop"
