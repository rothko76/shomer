"""The only place that talks to an LLM. OpenAI-compatible: OpenRouter primary, Ollama fallback."""

from dataclasses import dataclass
from typing import Any, Protocol

import openai
import structlog
from openai import OpenAI
from openai.types.chat import ChatCompletion
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from shomer.config import Settings
from shomer.metrics import LLM_REQUESTS, LLM_TOKENS

log = structlog.get_logger(__name__)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, openai.APIConnectionError | openai.APITimeoutError | openai.RateLimitError):
        return True
    return isinstance(exc, openai.APIStatusError) and exc.status_code in {408, 409, 429, 500, 502, 503, 504}


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatCompletion: ...


@dataclass
class _Endpoint:
    client: OpenAI
    model: str

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(multiplier=1, max=10),
        retry=retry_if_exception(_retryable),
        reraise=True,
    )
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatCompletion:
        # Empty `tools` = force a final answer; some providers reject an empty tools list.
        extra: dict[str, Any] = {"tools": tools, "tool_choice": "auto"} if tools else {}
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0,
            **extra,
        )
        if resp.usage:
            LLM_TOKENS.labels(self.model, "prompt").inc(resp.usage.prompt_tokens)
            LLM_TOKENS.labels(self.model, "completion").inc(resp.usage.completion_tokens)
        return resp


class LLM:
    """Primary endpoint with an optional fallback, tried once the primary exhausts its retries."""

    def __init__(self, settings: Settings) -> None:
        self._endpoints = [
            _Endpoint(
                OpenAI(
                    base_url=settings.llm_base_url,
                    api_key=settings.llm_api_key.get_secret_value() or "unset",
                    timeout=settings.llm_timeout_seconds,
                    max_retries=0,  # tenacity owns retries
                ),
                settings.llm_model,
            )
        ]
        if settings.llm_fallback_base_url and settings.llm_fallback_model:
            self._endpoints.append(
                _Endpoint(
                    OpenAI(
                        base_url=settings.llm_fallback_base_url,
                        api_key="ollama",  # Ollama ignores it, the SDK requires one
                        timeout=settings.llm_timeout_seconds * 3,  # local models are slower
                        max_retries=0,
                    ),
                    settings.llm_fallback_model,
                )
            )

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatCompletion:
        last_err: Exception | None = None
        for endpoint in self._endpoints:
            try:
                resp = endpoint.complete(messages, tools)
            except openai.OpenAIError as err:
                LLM_REQUESTS.labels(endpoint.model, "error").inc()
                log.warning("llm_endpoint_failed", model=endpoint.model, error=str(err))
                last_err = err
                continue
            LLM_REQUESTS.labels(endpoint.model, "ok").inc()
            return resp
        assert last_err is not None
        raise last_err
