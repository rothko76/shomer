import json
from types import SimpleNamespace as NS
from typing import Any

import pytest
from kubernetes.client.exceptions import ApiException

from shomer.tools import REGISTRY, k8s


def _pod(name: str, phase: str, restarts: int = 0, waiting: str | None = None) -> NS:
    state = NS(waiting=NS(reason=waiting, message="back-off") if waiting else None)
    return NS(
        metadata=NS(name=name),
        spec=NS(node_name="kind-worker"),
        status=NS(phase=phase, container_statuses=[NS(name="app", restart_count=restarts, state=state)]),
    )


class FakeCore:
    def __init__(self, pods: list[NS] | None = None, error: ApiException | None = None) -> None:
        self.pods = pods or []
        self.error = error
        self.log_kwargs: dict[str, Any] = {}

    def list_namespaced_pod(self, namespace: str) -> NS:
        if self.error:
            raise self.error
        return NS(items=self.pods)

    def read_namespaced_pod_log(self, **kwargs: Any) -> str:
        self.log_kwargs = kwargs
        return "panic: missing DB_URL"


@pytest.fixture
def fake_core(monkeypatch: pytest.MonkeyPatch) -> FakeCore:
    fake = FakeCore(
        [_pod("ok", "Running"), _pod("crashy", "Running", 7, "CrashLoopBackOff"), _pod("new", "Pending")]
    )
    monkeypatch.setattr(k8s, "core", lambda: fake)
    return fake


def test_get_failed_pods_sorted_worst_first(fake_core: FakeCore) -> None:
    out, ok = REGISTRY.call("get_failed_pods", {"namespace": "shop"}, 10_000)
    rows = json.loads(out)
    assert ok
    assert [r["name"] for r in rows] == ["crashy", "new"]
    assert rows[0]["waiting"][0]["reason"] == "CrashLoopBackOff"


def test_get_pod_logs_passes_previous_and_tail(fake_core: FakeCore) -> None:
    out, ok = REGISTRY.call(
        "get_pod_logs", {"namespace": "shop", "pod_name": "crashy", "previous": True, "tail": 50}, 10_000
    )
    assert ok and "missing DB_URL" in out
    assert fake_core.log_kwargs["previous"] is True and fake_core.log_kwargs["tail_lines"] == 50


def test_api_errors_become_tool_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(k8s, "core", lambda: FakeCore(error=ApiException(status=403, reason="Forbidden")))
    out, ok = REGISTRY.call("get_pods", {"namespace": "kube-system"}, 10_000)
    assert not ok and "403 Forbidden" in out


def test_namespace_is_required() -> None:
    out, ok = REGISTRY.call("get_pods", {}, 10_000)
    assert not ok and "namespace" in out
