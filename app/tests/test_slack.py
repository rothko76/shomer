import json

import httpx

from shomer.agent.loop import Diagnosis, ToolCallRecord
from shomer.alerts import Alert
from shomer.notify.slack import SlackNotifier, build_blocks


def _diagnosis(alert: Alert, **kw: object) -> Diagnosis:
    base: dict[str, object] = {
        "alert": alert,
        "text": "*Summary:* broken",
        "model": "test-model",
        "steps": 3,
        "duration_seconds": 4.2,
        "tool_calls": [ToolCallRecord("get_pods", "{}", True), ToolCallRecord("get_pods", "{}", True)],
    }
    base.update(kw)
    return Diagnosis(**base)  # type: ignore[arg-type]


def test_blocks_content(alert: Alert) -> None:
    blocks = build_blocks(_diagnosis(alert))
    text = json.dumps(blocks)
    assert blocks[0]["text"]["text"].endswith("KubePodCrashLooping")
    assert "`shop`" in text and "*Summary:* broken" in text
    assert "Tools: get_pods" in text and "2 tool calls" in text
    assert any(b["type"] == "actions" for b in blocks)


def test_long_text_truncated_and_budget_flag(alert: Alert) -> None:
    blocks = build_blocks(_diagnosis(alert, text="x" * 5000, budget_exhausted=True))
    section = next(b for b in blocks if b["type"] == "section")
    assert len(section["text"]["text"]) == 3000
    assert "budget exhausted" in json.dumps(blocks)


def test_send_posts_json(alert: Alert) -> None:
    sent: list[httpx.Request] = []
    transport = httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(200, text="ok"))
    SlackNotifier("https://hooks.slack.test/x", httpx.Client(transport=transport)).send(_diagnosis(alert))
    body = json.loads(sent[0].content)
    assert body["blocks"] and "KubePodCrashLooping" in body["text"]
