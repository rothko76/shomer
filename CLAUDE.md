# shomer — autonomous SRE agent on a GitOps platform

Portfolio project. Full brief and scope: docs/PROJECT_BRIEF.md. Decisions: docs/adr/.
Current milestone: v1 (see README "Roadmap"). Don't build "later iterations" items unless asked.

## Layout & boundaries
- app/       Python agent. Must not import from or reference platform/ or charts/.
- charts/    Helm chart for the agent only. No platform components here.
- platform/  terraform/ provisions clusters; gitops/ is what ArgoCD syncs. CI never applies to clusters.
- scenarios/ fault-injection scripts for demos; target kind only.
Each top-level dir has its own path-filtered workflow — keep changes scoped to one dir per PR where possible.

## Commands
- App:      cd app && uv sync && uv run pytest && uv run ruff check . && uv run mypy src
- Run:      cd app && uv run uvicorn shomer.api:app --reload
- Cluster:  make up / make down (kind via Terraform) · make bootstrap (ArgoCD + root app)
- Chart:    helm lint charts/shomer && helm template charts/shomer | kubeconform -strict
- Infra:    cd platform/terraform/envs/kind && terraform fmt -check && terraform validate

## Rules
- Agent tools are READ-ONLY. RBAC is get/list/watch. Never add a mutating k8s tool or verb.
- LLM access goes through the OpenAI-compatible client in app/src/shomer/agent/llm.py (OpenRouter default, Ollama fallback via base_url). No provider SDKs elsewhere.
- Secrets: never commit plaintext. Use SealedSecrets in platform/gitops; .env for local dev (gitignored).
- Image tags in platform/gitops are bumped by CI only; don't hand-edit them.
- Don't run terraform apply/destroy, or kubectl against any context other than kind-*, without asking.
- Never commit terraform state or kubeconfigs.
- New significant decision → add an ADR (docs/adr/NNNN-title.md, short: context/decision/consequences).
- Every alert rule needs a runbook_url annotation pointing at docs/runbooks/.

## Conventions
- Python 3.12, type hints everywhere, pydantic models for tool I/O, structured JSON logging.
- Tests mock the LLM, k8s and Prometheus; integration tests are marked @pytest.mark.integration.
- Conventional commits (feat:, fix:, chore:, docs:, ci:).
