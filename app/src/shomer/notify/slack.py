"""Post diagnoses to Slack via an incoming webhook (Block Kit)."""

from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from shomer.agent.loop import Diagnosis

log = structlog.get_logger(__name__)

SECTION_LIMIT = 3000  # Slack's max text length for a section block


def build_blocks(d: Diagnosis) -> list[dict[str, Any]]:
    a = d.alert
    severity = a.labels.get("severity", "unknown")
    where = " · ".join(
        f"`{a.labels[k]}`" for k in ("namespace", "deployment", "pod", "service") if k in a.labels
    )
    tools_used = ", ".join(dict.fromkeys(t.name for t in d.tool_calls)) or "none"
    footer = f"{d.model} · {len(d.tool_calls)} tool calls · {d.duration_seconds:.1f}s"
    if d.budget_exhausted:
        footer += " · :warning: step budget exhausted"
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": f":rotating_light: {a.name}"[:150]}},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"*{severity}* {where}".strip()}],
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": d.text[:SECTION_LIMIT]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Tools: {tools_used}"[:SECTION_LIMIT]}]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]},
    ]
    if a.generator_url:
        blocks.insert(
            3,
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open in Prometheus"},
                        "url": a.generator_url,
                    }
                ],
            },
        )
    return blocks


class SlackNotifier:
    def __init__(self, webhook_url: str, client: httpx.Client | None = None) -> None:
        self._url = webhook_url
        self._client = client or httpx.Client(timeout=10.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(multiplier=1, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def send(self, d: Diagnosis) -> None:
        resp = self._client.post(
            self._url, json={"text": f"{d.alert.name}: diagnosis ready", "blocks": build_blocks(d)}
        )
        resp.raise_for_status()


class LogNotifier:
    """Used when no Slack webhook is configured (local dev): logs the diagnosis instead."""

    def send(self, d: Diagnosis) -> None:
        log.info("diagnosis", alert=d.alert.name, text=d.text, tools=[t.name for t in d.tool_calls])
