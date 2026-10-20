"""Read-only Prometheus tools (HTTP API v1)."""

import time
from functools import cache
from typing import Annotated, Any

import httpx
from pydantic import Field

from shomer.config import get_settings
from shomer.tools.registry import tool

MAX_SERIES = 20


@cache
def http_client() -> httpx.Client:
    return httpx.Client(base_url=get_settings().prometheus_url, timeout=15.0)


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = http_client().get(path, params=params)
    except httpx.HTTPError as err:
        return {"error": f"prometheus unreachable: {err}"}
    body: dict[str, Any] = (
        resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    )
    if resp.status_code != 200 or body.get("status") != "success":
        return {"error": f"prometheus {resp.status_code}: {body.get('error', resp.text[:300])}"}
    data: dict[str, Any] = body["data"]
    result = data.get("result", [])
    if isinstance(result, list) and len(result) > MAX_SERIES:
        data = {
            **data,
            "result": result[:MAX_SERIES],
            "note": f"showing {MAX_SERIES} of {len(result)} series",
        }
    return data


@tool
def prometheus_query(query: Annotated[str, Field(description="PromQL expression")]) -> dict[str, Any]:
    """Evaluate a PromQL instant query, e.g. rate(container_cpu_usage_seconds_total[5m])."""
    return _get("/api/v1/query", {"query": query})


@tool
def prometheus_query_range(
    query: Annotated[str, Field(description="PromQL expression")],
    minutes: Annotated[int, Field(ge=5, le=360, description="Look-back window")] = 30,
    step_seconds: Annotated[int, Field(ge=15, le=600)] = 60,
) -> dict[str, Any]:
    """Evaluate a PromQL query over the last N minutes, to see trends around the alert."""
    end = time.time()
    return _get(
        "/api/v1/query_range",
        {"query": query, "start": end - minutes * 60, "end": end, "step": step_seconds},
    )


@tool
def get_firing_alerts() -> dict[str, Any]:
    """Alerts currently firing in Prometheus, to spot related or cascading failures."""
    return _get("/api/v1/alerts", {})
