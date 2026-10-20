# shomer

Autonomous SRE agent that investigates Kubernetes alerts, running on a GitOps platform with SLOs,
chaos testing, and supply-chain security.

> Work in progress. See [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) for the full brief and
> [docs/adr/](docs/adr/) for design decisions.

## Roadmap — v1

**M0 – Repo foundation**
- [x] CLAUDE.md, README skeleton, `.gitignore`, Makefile, ADR-0001 (monorepo) and ADR-0002 (tag bumps)
- [ ] Branch protection on `master` (PR required, status checks)

**M1 – Agent app (local)**
- [x] `app/` with uv, ruff, mypy, pytest. Port read-only k8s tools from ai-ops-agent (drop mutating tools, approval gate, weather, Redis)
- [x] OpenAI-compatible LLM client (OpenRouter, Ollama fallback); agent loop with a max-steps cap
- [x] Prometheus query tool
- [x] `/webhook/alertmanager` → investigate → Slack message (Block Kit), `/healthz`, `/metrics` (request latency/errors for the SLO)
- [x] Unit tests with mocked LLM, k8s and Prometheus

**M2 – CI**
- [ ] `app-ci.yml`: lint, test, multi-stage non-root image, Trivy (fail on HIGH/CRITICAL), Syft SBOM attached, cosign keyless sign, push GHCR
- [ ] `chart-ci.yml`, `platform-ci.yml` (lint/validate only)

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
workloads), EKS, Argo Rollouts canary, Loki/Tempo, MCP tool server, fix PRs, chaos + postmortem.
Full list in the [brief](docs/PROJECT_BRIEF.md#later-iterations).

## Credits
The starting idea comes from the DevOps mentor–mentee group roadmap
([yehudasho/dinghy-mentor-mentee](https://github.com/yehudasho/dinghy-mentor-mentee)).
This repo is my own design, not a fork.
