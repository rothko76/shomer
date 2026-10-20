# ADR-0001: Monorepo, started fresh, porting code from ai-ops-agent

- Status: Accepted
- Date: 2026-10-19

## Context
The project has two halves: the SRE agent app and the platform it runs on (Terraform, ArgoCD,
observability, security). The brief left open whether they share one repo or live in two, and
whether to evolve the existing `rothko76/ai-ops-agent` repo.

`ai-ops-agent` has 12 commits. It is built on the OpenAI Responses API, with a CLI, mutating
tools behind an approval gate, a demo weather tool, and Redis memory. This project needs an
OpenAI-compatible client (OpenRouter, with Ollama as fallback), read-only tools, and an
Alertmanager webhook trigger, so the core loop gets rewritten either way. The parts worth keeping
are files, not history: the read-only k8s tools, the fault scenarios, the tests as a reference,
and the kind Terraform.

## Decision
- One repo (`shomer`), with strict top-level boundaries: `app/`, `charts/`, `platform/`,
  `scenarios/`, `docs/`. Each has its own path-filtered GitHub Actions workflow.
- Start fresh. Code from `ai-ops-agent` is copied in, and the porting commit records its origin
  (`ported from rothko76/ai-ops-agent@3958ec6`). That history is not imported.
- `ai-ops-agent` is archived on GitHub, with a README pointer to this repo.
- v1 runs on a single kind cluster. The old repo's hub/spoke (mgmt + target) Terraform layout is deferred.

## Consequences
- One README, diagram and CI story for reviewers. No version coordination across repos.
- ArgoCD watches the same repo that CI writes image tags to. Tag bumps must only touch
  `platform/gitops/**`, and app workflows filter on `app/**`, so a tag bump can't trigger a CI loop
  (see ADR-0002).
- Boundaries are enforced by convention (CLAUDE.md, path filters, review), not by repo permissions.
- Splitting later is still possible with `git filter-repo --subdirectory-filter`.
