# Sourced by scenario scripts. Usage: require_kind_context "$1"
require_kind_context() {
  local ctx="${1:-}"
  if [[ ! "$ctx" =~ ^kind- ]]; then
    echo "refusing to run: context '$ctx' is not a kind-* context" >&2
    exit 1
  fi
  KUBECTL=(kubectl --context "$ctx")
}
