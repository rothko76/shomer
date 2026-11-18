# shomer

Autonomous SRE agent that investigates Kubernetes alerts, running on a GitOps platform with SLOs,
chaos testing, and supply-chain security.

> Work in progress. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) for the full brief and
> [docs/adr/](docs/adr/) for design decisions.


## How it works

1. **Alert in.** Alertmanager POSTs to `/webhook/alertmanager` with a bearer token
   (`SHOMER_WEBHOOK_TOKEN`); requests without a valid token get a 401.
2. **Filter.** Only `firing` alerts are investigated, and each fingerprint at most once per
   dedupe window (15 min), since Alertmanager re-sends firing alerts every `repeat_interval`.
3. **Ack fast.** The service returns `202 Accepted` immediately and investigates in a background
   task, so Alertmanager doesn't time out and retry. At most 2 investigations run at once.
4. **Investigate.** An LLM tool-calling loop: each step the model either calls a read-only tool
   (Kubernetes pods/events/logs, Prometheus queries) and gets the result back, or returns a
   diagnosis. Bounded by `max_steps` (then a forced final answer) and a duplicate-call guard.
5. **Notify.** The diagnosis is posted to Slack (Block Kit), or logged when no webhook is set.
6. **Observe.** `/metrics` exposes request latency/errors (for the agent's SLO), investigation
   outcomes, tool calls and LLM token usage.

**Safety:** the agent can't change the cluster. Its tools only call read APIs, a test
(`tests/test_readonly.py`) fails CI on any mutating Kubernetes call, and read-only RBAC
(get/list/watch) is planned with the Helm chart (M3).

## Running locally

```bash
make up                                  # kind cluster "shomer" via Terraform
make scenario SCENARIO=crashloop         # inject a fault
cd app && cp .env.example .env           # set SHOMER_LLM_API_KEY
uv sync && uv run uvicorn --factory shomer.api:app
./scenarios/fire-alert.sh crashloop      # send the matching Alertmanager payload
```

## Roadmap — v1

**M0 – Repo foundation**
- [x] CLAUDE.md, README skeleton, `.gitignore`, Makefile, ADR-0001 (monorepo) and ADR-0002 (tag bumps)
- [x] Branch protection on `master` (PR required, status checks)

**M1 – Agent app (local)**
- [x] `app/` with uv, ruff, mypy, pytest. Port read-only k8s tools from ai-ops-agent (drop mutating tools, approval gate, weather, Redis)
- [x] OpenAI-compatible LLM client (OpenRouter, Ollama fallback); agent loop with a max-steps cap
- [x] Prometheus query tool
- [x] `/webhook/alertmanager` → investigate → Slack message (Block Kit), `/healthz`, `/metrics` (request latency/errors for the SLO)
- [x] Unit tests with mocked LLM, k8s and Prometheus

**M2 – CI**
- [ ] `app-ci.yml`: lint, test, multi-stage non-root image, Trivy (fail on HIGH/CRITICAL), Syft SBOM attached, cosign keyless sign, push GHCR
- [ ] Keyless signing via GitHub Actions OIDC (`id-token: write` on the signing job only); `cosign verify` with pinned certificate identity and issuer
- [ ] `chart-ci.yml`, `platform-ci.yml` (lint/validate only)
- [ ] Dependency scanning in app-ci (pip-audit or osv-scanner)
- [ ] Dependabot with a cooldown for pip and GitHub Actions
- [x] GitHub Actions pinned by commit SHA (already done in secrets-scan)

**M3 – Platform on kind**
- [x] Terraform `modules/kind-cluster` + `envs/kind` (single cluster, ingress port mappings)
- [ ] ArgoCD installed + root app-of-apps bootstrapped (`make up && make bootstrap` from zero)
- [ ] Sealed Secrets controller; sealed OpenRouter key + Slack webhook
- [ ] Helm chart `charts/shomer` (read-only RBAC, ServiceMonitor, NetworkPolicy, restricted Pod Security)
- [ ] Agent deployed via ArgoCD, image tag bump flows CI → Git → ArgoCD sync

**M4 – Observability + SLO**
- [ ] kube-prometheus-stack via ArgoCD (Prometheus, Grafana, Alertmanager)
- [ ] One SLO (agent webhook availability or latency) via Sloth → multi-window burn-rate alerts
- [ ] Alertmanager route: workload alerts → agent webhook. Grafana dashboard as code
- [ ] Runbook for the SLO alert

**M5 – End-to-end + PR reviewer**
- [ ] Port one scenario (e.g. crashloop) → alert fires → agent posts diagnosis to Slack
- [ ] `claude-review.yml` (claude-code-action@v1) with per-run, per-workflow and account guardrails from the brief

**M6 – Publish**
- [ ] README: architecture diagram, quickstart, design decisions, "what I'd do in production"
- [ ] Archive ai-ops-agent with a pointer; make repo public; tag `v1.0.0`

Stretch: kind integration test inside the CI runner (otherwise first item in v1.1).

**Later:** two-cluster split (management cluster for ArgoCD + agent, target cluster for
workloads), EKS (with GitHub Actions OIDC → AWS IAM role instead of static keys, and IRSA/Pod Identity for the agent), Argo Rollouts canary, Loki/Tempo, MCP tool server, fix PRs, chaos + postmortem.
Full list in the [brief](docs/PROJECT_BRIEF.md#later-iterations).

## Credits
The starting idea comes from the DevOps mentor–mentee group roadmap
([yehudasho/dinghy-mentor-mentee](https://github.com/yehudasho/dinghy-mentor-mentee)).
This repo is my own design, not a fork.
