from datetime import UTC, datetime
from typing import Any

import pytest
from openai.types.chat import ChatCompletion

from shomer.alerts import Alert


def make_alert(**overrides: Any) -> Alert:
    data: dict[str, Any] = {
        "status": "firing",
        "labels": {
            "alertname": "KubePodCrashLooping",
            "namespace": "shop",
            "pod": "web-1",
            "severity": "warning",
        },
        "annotations": {"summary": "Pod shop/web-1 is crash looping"},
        "startsAt": datetime(2026, 10, 20, 9, 0, tzinfo=UTC).isoformat(),
        "generatorURL": "http://prometheus/graph?g0.expr=up",
        "fingerprint": "abc123",
    }
    data.update(overrides)
    return Alert.model_validate(data)


def completion(content: str | None = None, tool_calls: list[tuple[str, str]] | None = None) -> ChatCompletion:
    """Build a ChatCompletion; tool_calls is [(name, json_args), ...]."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {"id": f"call_{i}", "type": "function", "function": {"name": n, "arguments": a}}
            for i, (n, a) in enumerate(tool_calls)
        ]
    return ChatCompletion.model_validate(
        {
            "id": "cmpl",
            "object": "chat.completion",
            "created": 0,
            "model": "test-model",
            "choices": [
                {"index": 0, "finish_reason": "tool_calls" if tool_calls else "stop", "message": message}
            ],
        }
    )


class ScriptedLLM:
    """Returns pre-baked completions in order and records what it was sent."""

    def __init__(self, *responses: ChatCompletion) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatCompletion:
        self.calls.append(([dict(m) for m in messages], tools))
        return self.responses.pop(0)


@pytest.fixture
def alert() -> Alert:
    return make_alert()
