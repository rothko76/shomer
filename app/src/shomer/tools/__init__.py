"""Read-only investigation tools. Importing this package registers all tools."""

from shomer.tools import k8s, prometheus  # noqa: F401  (registration side effect)
from shomer.tools.registry import REGISTRY, Tool, ToolRegistry, tool

__all__ = ["REGISTRY", "Tool", "ToolRegistry", "tool"]
