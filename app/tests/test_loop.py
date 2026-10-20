from typing import Any

from shomer.agent.loop import BUDGET_EXHAUSTED, Investigator
from shomer.alerts import Alert
from shomer.tools.registry import ToolRegistry
from tests.conftest import ScriptedLLM, completion


def _registry(calls: list[dict[str, Any]]) -> ToolRegistry:
    reg = ToolRegistry()

    @reg.register
    def get_failed_pods(namespace: str) -> list[dict[str, str]]:
        """Unhealthy pods."""
        calls.append({"namespace": namespace})
        return [{"name": "web-1", "reason": "CrashLoopBackOff"}]

    return reg


def test_tool_call_then_answer(alert: Alert) -> None:
    calls: list[dict[str, Any]] = []
    llm = ScriptedLLM(
        completion(tool_calls=[("get_failed_pods", '{"namespace": "shop"}')]),
        completion("*Summary:* web-1 crash loops."),
    )
    d = Investigator(llm, max_steps=5, max_tool_output_chars=1000, registry=_registry(calls)).investigate(
        alert
    )

    assert d.text == "*Summary:* web-1 crash loops."
    assert calls == [{"namespace": "shop"}]
    assert [t.name for t in d.tool_calls] == ["get_failed_pods"] and d.tool_calls[0].ok
    assert d.steps == 2 and not d.budget_exhausted
    # second request carries the assistant tool call + the tool result, linked by id
    sent = llm.calls[1][0]
    assert sent[-2]["role"] == "assistant" and sent[-2]["tool_calls"][0]["id"] == "call_0"
    assert sent[-1] == {"role": "tool", "tool_call_id": "call_0", "content": sent[-1]["content"]}
    assert "CrashLoopBackOff" in sent[-1]["content"]
    # the alert itself reaches the model
    assert "KubePodCrashLooping" in llm.calls[0][0][1]["content"]


def test_duplicate_calls_not_re_executed(alert: Alert) -> None:
    calls: list[dict[str, Any]] = []
    same = ("get_failed_pods", '{"namespace": "shop"}')
    reordered = ("get_failed_pods", '{ "namespace":"shop" }')
    llm = ScriptedLLM(completion(tool_calls=[same]), completion(tool_calls=[reordered]), completion("done"))
    d = Investigator(llm, 5, 1000, registry=_registry(calls)).investigate(alert)
    assert len(calls) == 1 and len(d.tool_calls) == 1
    assert "duplicate" in llm.calls[2][0][-1]["content"]


def test_step_budget_forces_final_answer_without_tools(alert: Alert) -> None:
    calls: list[dict[str, Any]] = []
    llm = ScriptedLLM(
        completion(tool_calls=[("get_failed_pods", '{"namespace": "a"}')]),
        completion(tool_calls=[("get_failed_pods", '{"namespace": "b"}')]),
        completion("partial diagnosis"),
    )
    d = Investigator(llm, max_steps=2, max_tool_output_chars=1000, registry=_registry(calls)).investigate(
        alert
    )
    assert d.budget_exhausted and d.text == "partial diagnosis"
    last_messages, last_tools = llm.calls[-1]
    assert last_tools == []
    assert last_messages[-1] == {"role": "user", "content": BUDGET_EXHAUSTED}


def test_empty_answer_gets_placeholder(alert: Alert) -> None:
    d = Investigator(ScriptedLLM(completion("")), 3, 1000, registry=ToolRegistry()).investigate(alert)
    assert "no diagnosis" in d.text
