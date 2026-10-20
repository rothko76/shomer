"""Guardrail: the agent must never be able to change the cluster."""

import ast
from pathlib import Path

import shomer.tools.k8s as k8s_module
from shomer.tools import REGISTRY

MUTATING_PREFIXES = ("create_", "patch_", "delete_", "replace_", "connect_")
MUTATING_WORDS = ("create", "delete", "patch", "set", "restart", "rollback", "scale", "apply", "exec")


def test_k8s_module_only_calls_read_apis() -> None:
    tree = ast.parse(Path(k8s_module.__file__).read_text())
    offenders = [
        f"line {node.lineno}: {node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr.startswith(MUTATING_PREFIXES)
    ]
    assert not offenders, f"mutating Kubernetes API calls found: {offenders}"


def test_no_tool_name_suggests_mutation() -> None:
    for name in REGISTRY.names():
        verb = name.split("_")[0]
        assert verb not in MUTATING_WORDS, f"tool '{name}' looks mutating"
