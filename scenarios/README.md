# Fault scenarios

Ported from `rothko76/ai-ops-agent` (`manifests/labs/scenarios`). Each scenario has:

- `scenario.yaml`: the broken workload
- `start.sh <context>` / `cleanup.sh <context>`: these refuse to run against anything but a `kind-*` context
- `alert.json`: the Alertmanager payload that kube-prometheus-stack would send for this fault, so
  you can trigger the agent before Prometheus is installed (`./scenarios/fire-alert.sh crashloop`)

| Scenario | Fault | What the agent should find |
|---|---|---|
| `crashloop` | app exits at startup | `CrashLoopBackOff`; previous logs show `DATABASE_URL` is not set |

Usage: `make scenario SCENARIO=crashloop`, then `make scenario-cleanup SCENARIO=crashloop`.
