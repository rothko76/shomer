"""HTTP entrypoint: Alertmanager webhook, health and metrics."""

import hmac
import time
from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response, status
from prometheus_client import make_asgi_app
from starlette.routing import Match

from shomer.agent.llm import LLM
from shomer.agent.loop import Investigator
from shomer.alerts import AlertmanagerPayload
from shomer.config import Settings, get_settings
from shomer.log import configure_logging
from shomer.metrics import HTTP_LATENCY, HTTP_REQUESTS
from shomer.notify.slack import LogNotifier, SlackNotifier
from shomer.service import AlertService, Notifier

log = structlog.get_logger(__name__)


def build_service(settings: Settings) -> AlertService:
    notifier: Notifier = (
        SlackNotifier(settings.slack_webhook_url.get_secret_value())
        if settings.slack_webhook_url
        else LogNotifier()
    )
    return AlertService(
        investigator=Investigator(LLM(settings), settings.max_steps, settings.max_tool_output_chars),
        notifier=notifier,
        max_concurrent=settings.max_concurrent_investigations,
        dedupe_window_seconds=settings.dedupe_window_seconds,
    )


def create_app(settings: Settings | None = None, service: AlertService | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    app = FastAPI(title="shomer", docs_url=None, redoc_url=None)
    app.state.service = service or build_service(settings)
    app.mount("/metrics", make_asgi_app())

    @app.middleware("http")
    async def record_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Label by route template, not raw path, to keep cardinality bounded.
        route = next(
            (
                getattr(r, "path", "unmatched")
                for r in app.router.routes
                if r.matches(request.scope)[0] == Match.FULL
            ),
            "unmatched",
        )
        if route == "/metrics":
            return await call_next(request)
        start = time.perf_counter()
        code = 500
        try:
            response = await call_next(request)
            code = response.status_code
            return response
        finally:
            HTTP_LATENCY.labels(route, request.method).observe(time.perf_counter() - start)
            HTTP_REQUESTS.labels(route, request.method, str(code)).inc()

    def check_token(authorization: Annotated[str | None, Header()] = None) -> None:
        if settings.webhook_token is None:
            return
        expected = f"Bearer {settings.webhook_token.get_secret_value()}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing bearer token")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/webhook/alertmanager",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(check_token)],
    )
    def alertmanager_webhook(payload: AlertmanagerPayload, background: BackgroundTasks) -> dict[str, int]:
        # Ack fast (Alertmanager times out and retries); investigate in the background.
        svc: AlertService = app.state.service
        accepted = [a for a in payload.alerts if svc.should_investigate(a)]
        for alert in accepted:
            background.add_task(svc.handle, alert)
        log.info("webhook_received", alerts=len(payload.alerts), accepted=len(accepted))
        return {"received": len(payload.alerts), "accepted": len(accepted)}

    return app


def app() -> FastAPI:
    """Factory for `uvicorn --factory shomer.api:app`."""
    return create_app()
