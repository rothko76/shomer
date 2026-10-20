import json

import httpx
import pytest

from shomer.tools import REGISTRY, prometheus


def _install(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    client = httpx.Client(base_url="http://prom", transport=handler)
    monkeypatch.setattr(prometheus, "http_client", lambda: client)


def test_query_success_and_series_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        series = [{"metric": {"pod": f"p{i}"}, "value": [0, "1"]} for i in range(30)]
        return httpx.Response(
            200, json={"status": "success", "data": {"resultType": "vector", "result": series}}
        )

    _install(monkeypatch, httpx.MockTransport(handler))
    out, ok = REGISTRY.call("prometheus_query", {"query": "up"}, 100_000)
    data = json.loads(out)
    assert ok
    assert seen[0].url.params["query"] == "up"
    assert len(data["result"]) == prometheus.MAX_SERIES and "30 series" in data["note"]


def test_bad_promql_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"status": "error", "error": "parse error"})

    _install(monkeypatch, httpx.MockTransport(handler))
    out, ok = REGISTRY.call("prometheus_query", {"query": "up{"}, 10_000)
    assert not ok and "parse error" in out


def test_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    _install(monkeypatch, httpx.MockTransport(handler))
    out, ok = REGISTRY.call("get_firing_alerts", {}, 10_000)
    assert not ok and "unreachable" in out
