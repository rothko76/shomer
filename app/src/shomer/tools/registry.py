"""Tool registry: one decorator turns a typed function into an LLM tool.

The JSON schema the model sees is generated from the function signature, and the model's
arguments are validated against it before the function runs. This replaces the hand-written
schemas + dispatch if-chain from ai-ops-agent.
"""

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ValidationError, create_model

ToolFunc = Callable[..., Any]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    func: ToolFunc
    args_model: type[BaseModel]

    def openai_schema(self) -> dict[str, Any]:
        params = self.args_model.model_json_schema()
        params.pop("title", None)
        for prop in params.get("properties", {}).values():
            prop.pop("title", None)
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": params},
        }


def _args_model(func: ToolFunc) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for name, param in inspect.signature(func).parameters.items():
        if param.annotation is inspect.Parameter.empty:
            raise TypeError(f"tool {func.__name__}: parameter '{name}' needs a type annotation")
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (param.annotation, default)
    model: type[BaseModel] = create_model(f"{func.__name__}_args", **fields)
    return model


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, func: ToolFunc) -> ToolFunc:
        name = func.__name__
        if name in self._tools:
            raise ValueError(f"duplicate tool name: {name}")
        description = inspect.cleandoc(func.__doc__ or "")
        if not description:
            raise ValueError(f"tool {name} needs a docstring; it is the description the model sees")
        self._tools[name] = Tool(name, description, func, _args_model(func))
        return func

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [self._tools[n].openai_schema() for n in self.names()]

    def call(self, name: str, raw_args: str | dict[str, Any], max_chars: int) -> tuple[str, bool]:
        """Run a tool. Returns (JSON result for the model, ok). Never raises."""
        tool_ = self._tools.get(name)
        if tool_ is None:
            return self._dump(
                {"error": f"unknown tool '{name}'", "available": self.names()}, max_chars
            ), False
        try:
            args = json.loads(raw_args or "{}") if isinstance(raw_args, str) else raw_args
            validated = tool_.args_model.model_validate(args)
        except (json.JSONDecodeError, ValidationError) as err:
            return self._dump({"error": f"invalid arguments for '{name}': {err}"}, max_chars), False
        try:
            result = tool_.func(**dict(validated))
        except Exception as err:  # a broken tool must not kill the investigation
            return self._dump({"error": f"{name} failed: {type(err).__name__}: {err}"}, max_chars), False
        ok = not (isinstance(result, dict) and "error" in result)
        return self._dump(result, max_chars), ok

    @staticmethod
    def _dump(result: Any, max_chars: int) -> str:
        text = json.dumps(result, default=_json_default)
        if len(text) > max_chars:
            text = text[:max_chars] + f"... [truncated {len(text) - max_chars} chars]"
        return text


REGISTRY = ToolRegistry()
tool = REGISTRY.register
