# Project Brief — first-responder (working name)

Portfolio project for DevOps / SRE / Platform Engineering roles. Inspired by a
DevOps mentor–mentee group roadmap (yehudasho/dinghy-mentor-mentee), but built as
my own design, in my own repo(s), not a fork.

## One-line description
Autonomous SRE agent that investigates Kubernetes alerts, running on a GitOps
platform with SLOs, chaos testing, and supply-chain security.

## The app: SRE agent
- FastAPI service with an LLM-backed agent (OpenRouter; Ollama as fallback).
- Read-only tools: query Prometheus, get pod status/events, read logs.
  Ideally exposed as an MCP server.
- Triggered by an Alertmanager webhook (non-interactive by default).
- Output: diagnosis posted to Slack; later, a PR with a proposed fix for a human to approve.
- Optional minimal web chat for demos.
- May evolve from my existing "k8s fix agent" project rather than starting from scratch.

## The platform
- Local kind cluster via Terraform (primary, always-on target).
- EKS as optional second environment from the same Terraform; spin up for demos, then destroy.
- ArgoCD app-of-apps, pull-based GitOps; environment differences via overlays (kind / eks).
- Observability: Prometheus, Grafana, Loki, Tempo (OpenTelemetry). SLOs for the agent
  (latency, error rate) with burn-rate alerts. Dashboards as code.
- Security: image scanning (Trivy/Grype), SBOM, cosign signing, Kyverno policy admitting
  only signed images, External Secrets / Sealed Secrets, NetworkPolicies, Pod Security.
- Reliability: Chaos Mesh experiments, Argo Rollouts canary gated on SLO metrics,
  HPA/KEDA autoscaling with k6 load tests.

## CI/CD
- GitHub Actions: lint, test, build multi-stage non-root image, scan, SBOM, sign, push to GHCR.
- Integration test on an ephemeral kind cluster inside the runner.
- CD via ArgoCD pulling from Git (CI never needs to reach the cluster).

## Claude Code agents in CI (anthropics/claude-code-action@v1)
Introduced in phases, each with its guardrails added at the same time:
1. PR reviewer — once repo + tests + basic CI exist (read-only, low risk).
2. CI fixer — once tests are reliable. Opens fix PRs on `claude/fix-*` branches.
3. Weekly dependency bumper — once Helm + kind deploy work in CI; verifies on throwaway kind.
4. Agent cost metrics into Prometheus/Grafana — once observability is up.

Guardrails:
- Per run: `--max-turns`, `--max-budget-usd`, cheaper model / lower `--effort` for routine
  jobs, explicit `--allowedTools`, `--disallowedTools` for WebFetch/MCP where not needed.
- Per workflow: `timeout-minutes`, `concurrency` groups, path filters, skip drafts,
  loop guard (ignore `claude/*` branches), optional label gate.
- Account: dedicated Claude Console workspace with a monthly spend limit for CI keys.
- Blast radius: PRs only, branch protection, no merge rights, no cloud credentials.

## Documentation deliverables
- README: architecture diagram, quickstart, design decisions, "what I'd do in production",
  credit to the mentor group as the starting idea.
- Runbooks linked from alerts; one blameless postmortem from a chaos experiment; ADRs.
- Demo recording: inject fault → alert → agent diagnosis in Slack → fix PR → merge →
  ArgoCD sync → SLO recovers.

## v1 scope (finish and publish first)
- kind via Terraform, ArgoCD bootstrapped, agent deployed via GitOps.
- CI: test, scan, sign, push.
- Prometheus + Grafana, one SLO + alert.
- Agent triggered by alert, posts to Slack.
- PR reviewer agent.
- README with diagram.

## Later iterations
Two-cluster split (management cluster for ArgoCD + agent, target cluster for workloads),
EKS environment, Argo Rollouts canary, Loki/Tempo, cost metrics, fix PRs, MCP tool server,
CI fixer, dependency bumper, chaos + postmortem + runbooks, demo video.

## Deliberately out of scope
- n8n (doesn't strengthen the DevOps story).
- MongoDB, unless the agent needs state (then via an operator with backups).
- ELK (Loki instead; lighter on kind).

## Open decisions
- Monorepo vs two repos (platform + agent). Leaning: monorepo with strict boundaries
  (`app/`, `chart/`, `platform/`, path-filtered workflows) if starting fresh; two repos if
  evolving the existing k8s fix agent repo with history worth keeping.
- Final name (candidates: first-responder, nightwatch, triage, pager-zero).
