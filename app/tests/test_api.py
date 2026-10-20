from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from shomer.agent.loop import Diagnosis, Investigator
from shomer.alerts import Alert
from shomer.api import create_app
from shomer.config import Settings
from shomer.service import AlertService
from shomer.tools.registry import ToolRegistry
from tests.conftest import ScriptedLLM, completion, make_alert


class Collect:
    def __init__(self) -> None:
        self.sent: list[Diagnosis] = []

    def send(self, d: Diagnosis) -> None:
        self.sent.append(d)


def _payload(*alerts: Alert) -> dict[str, Any]:
    return {
        "version": "4",
        "status": "firing",
        "receiver": "shomer",
        "groupKey": "{}:{}",
        "alerts": [a.model_dump(mode="json", by_alias=True) for a in alerts],
    }


@pytest.fixture
def setup() -> tuple[TestClient, Collect, ScriptedLLM]:
    llm = ScriptedLLM(*[completion("diagnosis") for _ in range(5)])
    notifier = Collect()
    service = AlertService(Investigator(llm, 3, 1000, ToolRegistry()), notifier, 2, 900)
    settings = Settings(webhook_token=SecretStr("s3cret"), log_json=False)
    return TestClient(create_app(settings, service)), notifier, llm


AUTH = {"Authorization": "Bearer s3cret"}


def test_healthz(setup: tuple[TestClient, Collect, ScriptedLLM]) -> None:
    client, _, _ = setup
    assert client.get("/healthz").json() == {"status": "ok"}


def test_webhook_requires_token(setup: tuple[TestClient, Collect, ScriptedLLM]) -> None:
    client, notifier, _ = setup
    assert client.post("/webhook/alertmanager", json=_payload(make_alert())).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/webhook/alertmanager", json=_payload(make_alert()), headers=bad).status_code == 401
    assert notifier.sent == []


def test_webhook_investigates_firing_and_dedupes(setup: tuple[TestClient, Collect, ScriptedLLM]) -> None:
    client, notifier, _ = setup
    firing = make_alert()
    resolved = make_alert(status="resolved", fingerprint="zzz")
    r = client.post("/webhook/alertmanager", json=_payload(firing, resolved), headers=AUTH)
    assert r.status_code == 202 and r.json() == {"received": 2, "accepted": 1}
    assert [d.alert.fingerprint for d in notifier.sent] == ["abc123"]  # background task ran

    # Alertmanager repeat: same fingerprint inside the window is ignored
    r = client.post("/webhook/alertmanager", json=_payload(firing), headers=AUTH)
    assert r.json()["accepted"] == 0 and len(notifier.sent) == 1


def test_invalid_payload_rejected(setup: tuple[TestClient, Collect, ScriptedLLM]) -> None:
    client, _, _ = setup
    assert client.post("/webhook/alertmanager", json={"alerts": "x"}, headers=AUTH).status_code == 422


def test_metrics_exposed_with_route_labels(setup: tuple[TestClient, Collect, ScriptedLLM]) -> None:
    client, _, _ = setup
    client.get("/healthz")
    client.get("/does-not-exist")
    body = client.get("/metrics/").text
    assert 'shomer_http_requests_total{code="200",method="GET",route="/healthz"}' in body
    assert 'route="unmatched"' in body
    assert "/does-not-exist" not in body


def test_failed_investigation_is_contained() -> None:
    class Broken:
        def complete(self, *a: Any) -> Any:
            raise RuntimeError("llm down")

    notifier = Collect()
    service = AlertService(Investigator(Broken(), 3, 1000, ToolRegistry()), notifier, 1, 0)
    service.handle(make_alert())  # must not raise
    assert notifier.sent == []
