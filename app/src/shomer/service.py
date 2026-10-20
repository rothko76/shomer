"""Glue between the webhook and the investigator: dedupe, concurrency cap, notify, metrics."""

import threading
import time
from typing import Protocol

import structlog

from shomer.agent.loop import Diagnosis, Investigator
from shomer.alerts import Alert
from shomer.metrics import INVESTIGATION_DURATION, INVESTIGATIONS

log = structlog.get_logger(__name__)


class Notifier(Protocol):
    def send(self, d: Diagnosis) -> None: ...


class AlertService:
    def __init__(
        self,
        investigator: Investigator,
        notifier: Notifier,
        max_concurrent: int,
        dedupe_window_seconds: int,
    ) -> None:
        self.investigator = investigator
        self.notifier = notifier
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._dedupe_window = dedupe_window_seconds
        self._recent: dict[str, float] = {}
        self._lock = threading.Lock()

    def should_investigate(self, alert: Alert) -> bool:
        """Firing alerts only, and each fingerprint at most once per dedupe window.

        Alertmanager re-sends a firing group every repeat_interval; we don't pay for an LLM
        investigation each time.
        """
        if alert.status != "firing":
            return False
        key = alert.fingerprint or f"{alert.name}:{sorted(alert.labels.items())}"
        now = time.monotonic()
        with self._lock:
            self._recent = {k: t for k, t in self._recent.items() if now - t < self._dedupe_window}
            if key in self._recent:
                return False
            self._recent[key] = now
            return True

    def handle(self, alert: Alert) -> None:
        """Investigate one alert and notify. Runs in a background thread; never raises."""
        bound = log.bind(alert=alert.name, fingerprint=alert.fingerprint)
        with self._slots, INVESTIGATION_DURATION.time():
            try:
                diagnosis = self.investigator.investigate(alert)
            except Exception:
                INVESTIGATIONS.labels("llm_error").inc()
                bound.exception("investigation_failed")
                return
            try:
                self.notifier.send(diagnosis)
            except Exception:
                INVESTIGATIONS.labels("notify_error").inc()
                bound.exception("notify_failed")
                return
        outcome = "budget_exhausted" if diagnosis.budget_exhausted else "ok"
        INVESTIGATIONS.labels(outcome).inc()
        bound.info("investigation_done", steps=diagnosis.steps, tools=len(diagnosis.tool_calls))
