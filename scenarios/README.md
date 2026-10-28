# Fault scenarios

Ported from `rothko76/ai-ops-agent` (`manifests/labs/scenarios`). Each scenario has:

- `scenario.yaml`: the broken workload
- `start.sh <context>` / `cleanup.sh <context>`: these refuse to run against anything but a `kind-*` context
- `alert.json`: the Alertmanager payload that kube-prometheus-stack would send for this fault, so
  you can trigger the agent before Prometheus is installed (`./scenarios/fire-alert.sh crashloop`)

| Scenario | Fault | What the agent should find |
|---|---|---|
| `crashloop` | app exits at startup | `CrashLoopBackOff`; previous logs show `DATABASE_URL` is not set |
| `imagepull` | image tag doesn't exist in the registry (`busybox:1.63`, a typo for `1.36`) | `ErrImagePull` / `ImagePullBackOff`; pod events show `docker.io/library/busybox:1.63: not found` |

Usage: `make scenario SCENARIO=crashloop`, then `make scenario-cleanup SCENARIO=crashloop`.
