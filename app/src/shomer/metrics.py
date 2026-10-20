"""Prometheus metrics. HTTP metrics feed the agent's SLO; the rest explain cost and behaviour."""

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter("shomer_http_requests_total", "HTTP requests handled", ["route", "method", "code"])
HTTP_LATENCY = Histogram(
    "shomer_http_request_duration_seconds",
    "HTTP request latency",
    ["route", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
INVESTIGATIONS = Counter("shomer_investigations_total", "Alert investigations by outcome", ["outcome"])
INVESTIGATION_DURATION = Histogram(
    "shomer_investigation_duration_seconds",
    "End-to-end investigation time (alert received to Slack posted)",
    buckets=(1, 2.5, 5, 10, 20, 30, 60, 120, 300),
)
TOOL_CALLS = Counter("shomer_tool_calls_total", "Agent tool calls", ["tool", "outcome"])
LLM_TOKENS = Counter("shomer_llm_tokens_total", "LLM tokens used", ["model", "kind"])
LLM_REQUESTS = Counter("shomer_llm_requests_total", "LLM requests", ["model", "outcome"])
