# Thin entrypoints. Real logic lives in each directory's own tooling.
SHELL := /bin/bash
.DEFAULT_GOAL := help

TF_DIR       := platform/terraform/envs/kind
CLUSTER      ?= shomer
KUBE_CONTEXT := kind-$(CLUSTER)
SCENARIO     ?= crashloop

.PHONY: help up down bootstrap test lint scenario scenario-cleanup check-context

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

up: ## Create the kind cluster with Terraform
	terraform -chdir=$(TF_DIR) init -input=false
	terraform -chdir=$(TF_DIR) apply -input=false -auto-approve

down: ## Destroy the kind cluster
	terraform -chdir=$(TF_DIR) destroy -input=false -auto-approve

bootstrap: check-context ## Install ArgoCD and the root app-of-apps
	./platform/gitops/bootstrap/bootstrap.sh $(KUBE_CONTEXT)

test: ## Run app tests
	cd app && uv run pytest

lint: ## Lint app, chart and Terraform
	cd app && uv run ruff check . && uv run mypy src
	helm lint charts/shomer
	terraform -chdir=$(TF_DIR) fmt -check -recursive
	terraform -chdir=$(TF_DIR) validate

scenario: check-context ## Inject a fault scenario (SCENARIO=crashloop)
	./scenarios/$(SCENARIO)/start.sh $(KUBE_CONTEXT)

scenario-cleanup: check-context ## Remove a fault scenario
	./scenarios/$(SCENARIO)/cleanup.sh $(KUBE_CONTEXT)

# Guard: cluster-mutating targets only ever run against the local kind cluster.
check-context:
	@kubectl config get-contexts -o name | grep -qx '$(KUBE_CONTEXT)' \
	  || { echo "context $(KUBE_CONTEXT) not found (run 'make up' first)"; exit 1; }
