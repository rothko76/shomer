"""The investigation loop: alert in, diagnosis out. Bounded by max_steps; tools are read-only."""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from shomer.agent.llm import ChatModel
from shomer.agent.prompts import SYSTEM_PROMPT, alert_message
from shomer.alerts import Alert
from shomer.metrics import TOOL_CALLS
from shomer.tools import REGISTRY, ToolRegistry

log = structlog.get_logger(__name__)

BUDGET_EXHAUSTED = (
    "You have used your tool budget. Give your final answer now in the required format, "
    "based on the evidence so far, and state what you could not verify."
)


@dataclass
class ToolCallRecord:
    name: str
    arguments: str
    ok: bool


@dataclass
class Diagnosis:
    alert: Alert
    text: str
    model: str
    steps: int
    duration_seconds: float
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    budget_exhausted: bool = False


class Investigator:
    def __init__(
        self,
        llm: ChatModel,
        max_steps: int,
        max_tool_output_chars: int,
        registry: ToolRegistry = REGISTRY,
    ) -> None:
        self.llm = llm
        self.max_steps = max_steps
        self.max_tool_output_chars = max_tool_output_chars
        self.registry = registry

    def investigate(self, alert: Alert) -> Diagnosis:
        started = time.monotonic()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": alert_message(alert)},
        ]
        tools = self.registry.schemas()
        records: list[ToolCallRecord] = []
        seen: set[tuple[str, str]] = set()

        for step in range(1, self.max_steps + 2):
            exhausted = step > self.max_steps
            if exhausted:
                messages.append({"role": "user", "content": BUDGET_EXHAUSTED})
            resp = self.llm.complete(messages, [] if exhausted else tools)
            model = resp.model
            msg = resp.choices[0].message

            if not msg.tool_calls or exhausted:
                return Diagnosis(
                    alert=alert,
                    text=(msg.content or "").strip() or "_The model returned no diagnosis._",
                    model=model,
                    steps=step,
                    duration_seconds=time.monotonic() - started,
                    tool_calls=records,
                    budget_exhausted=exhausted,
                )

            messages.append(msg.model_dump(include={"role", "content", "tool_calls"}, exclude_none=True))
            for call in msg.tool_calls:
                if call.type != "function":
                    continue
                name, args = call.function.name, call.function.arguments
                key = (name, _normalize(args))
                if key in seen:
                    output, ok = '{"note": "duplicate call; same result as before"}', True
                else:
                    output, ok = self.registry.call(name, args, self.max_tool_output_chars)
                    seen.add(key)
                    TOOL_CALLS.labels(name, "ok" if ok else "error").inc()
                    records.append(ToolCallRecord(name, args, ok))
                log.info("tool_call", alert=alert.name, tool=name, args=args, ok=ok, step=step)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

        raise AssertionError("unreachable: the loop always returns on the budget-exhausted step")


def _normalize(args: str) -> str:
    try:
        return json.dumps(json.loads(args or "{}"), sort_keys=True)
    except json.JSONDecodeError:
        return args
