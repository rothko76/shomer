import json
from typing import Annotated

from pydantic import Field

from shomer.tools import REGISTRY
from shomer.tools.registry import ToolRegistry


def _registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.register
    def echo(text: str, times: Annotated[int, Field(ge=1, le=3)] = 1) -> dict[str, str]:
        """Repeat text."""
        return {"out": text * times}

    @reg.register
    def boom() -> dict[str, str]:
        """Always fails."""
        raise RuntimeError("kaput")

    return reg


def test_schema_generated_from_signature() -> None:
    schema = _registry().schemas()[1]["function"]
    assert schema["name"] == "echo"
    assert schema["description"] == "Repeat text."
    assert schema["parameters"]["required"] == ["text"]
    assert schema["parameters"]["properties"]["times"]["maximum"] == 3


def test_call_validates_and_runs() -> None:
    out, ok = _registry().call("echo", '{"text": "ab", "times": 2}', 1000)
    assert ok and json.loads(out) == {"out": "abab"}


def test_invalid_args_are_reported_not_raised() -> None:
    out, ok = _registry().call("echo", '{"text": "x", "times": 9}', 1000)
    assert not ok and "invalid arguments" in out
    out, ok = _registry().call("echo", "not json", 1000)
    assert not ok


def test_unknown_tool_and_exceptions() -> None:
    out, ok = _registry().call("nope", "{}", 1000)
    assert not ok and "unknown tool" in out
    out, ok = _registry().call("boom", "{}", 1000)
    assert not ok and "kaput" in out


def test_output_truncated() -> None:
    out, ok = _registry().call("echo", {"text": "x" * 500}, 100)
    assert ok and "truncated" in out and len(out) < 150


def test_all_real_tools_registered_with_valid_schemas() -> None:
    names = REGISTRY.names()
    assert {"get_failed_pods", "get_pod_logs", "prometheus_query", "get_rollout_history"} <= set(names)
    for schema in REGISTRY.schemas():
        assert schema["function"]["description"]
        assert schema["function"]["parameters"]["type"] == "object"
