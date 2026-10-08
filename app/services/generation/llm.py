from __future__ import annotations

import asyncio
import random
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.observability.metrics import metrics


class LLMError(Exception):
    category = "provider_error"


class LLMConfigurationError(LLMError):
    category = "configuration_error"


class LLMAuthenticationError(LLMError):
    category = "llm_provider_error"


class LLMRateLimitError(LLMError):
    category = "llm_rate_limit"


class LLMTimeoutError(LLMError):
    category = "llm_timeout"


class LLMTransientError(LLMError):
    category = "llm_provider_error"


class LLMUnavailableError(LLMError):
    category = "llm_provider_error"


class LLMProvider(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...


class GroqProvider:
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.timeout = settings.groq_timeout_seconds
        self.max_retries = settings.groq_max_retries
        self.max_output_tokens = settings.generation_max_output_tokens
        self._client = client

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        started = asyncio.get_running_loop().time()
        metrics.increment("llm_requests_total", provider="groq")
        if not self.api_key:
            metrics.increment("llm_failures_total", category="llm_provider_error")
            raise LLMConfigurationError("Groq is not configured")
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        self.endpoint,
                        headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                        json={"model": self.model, "temperature": 0, "max_tokens": self.max_output_tokens,
                              "response_format": {"type": "json_object"},
                              "messages": [{"role": "system", "content": system_prompt},
                                           {"role": "user", "content": user_prompt}]},
                    )
                except httpx.TimeoutException as exc:
                    if attempt < self.max_retries:
                        await asyncio.sleep(self._backoff(attempt))
                        continue
                    raise LLMTimeoutError("Groq request timed out") from exc
                except httpx.RequestError as exc:
                    if attempt < self.max_retries:
                        await asyncio.sleep(self._backoff(attempt))
                        continue
                    raise LLMUnavailableError("Groq could not be reached") from exc
                if response.status_code == 429:
                    metrics.increment("llm_rate_limits_total", provider="groq")
                    raise LLMRateLimitError("Groq rate limit reached")
                if response.status_code in (401, 403):
                    raise LLMAuthenticationError("Groq authentication failed")
                if 500 <= response.status_code < 600:
                    if attempt < self.max_retries:
                        await asyncio.sleep(self._backoff(attempt))
                        continue
                    metrics.increment("llm_5xx_total", provider="groq")
                    raise LLMTransientError("Groq returned a transient failure")
                if response.status_code >= 400:
                    raise LLMError("Groq rejected the request")
                try:
                    body: dict[str, Any] = response.json()
                    content = body["choices"][0]["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    raise LLMError("Groq returned an invalid response") from exc
                if not isinstance(content, str) or not content.strip():
                    raise LLMError("Groq returned empty content")
                metrics.increment("llm_successes_total", provider="groq")
                return content
            raise LLMUnavailableError("Groq request was not completed")
        except LLMError as exc:
            metrics.increment("llm_failures_total", category=getattr(exc, "category", "llm_provider_error"))
            if isinstance(exc, LLMTimeoutError):
                metrics.increment("llm_timeouts_total", provider="groq")
            raise
        finally:
            metrics.observe("llm_latency_ms", (asyncio.get_running_loop().time() - started) * 1000, provider="groq")
            if own_client:
                await client.aclose()

    def _backoff(self, attempt: int) -> float:
        return float(min(4.0, 0.25 * (2**attempt)) + random.uniform(0, 0.1))
