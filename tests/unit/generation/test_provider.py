import httpx
import pytest

from app.core.config import Settings
from app.services.generation.llm import GroqProvider, LLMRateLimitError, LLMTimeoutError


@pytest.mark.asyncio
async def test_groq_429_is_normalized_without_retry() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = GroqProvider(Settings(groq_api_key="test", groq_max_retries=2), client)
        with pytest.raises(LLMRateLimitError):
            await provider.generate("system", "user")
        assert calls == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_groq_retries_transient_5xx() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]}, request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = GroqProvider(Settings(groq_api_key="test", groq_max_retries=2), client)
        assert await provider.generate("system", "user") == "{}"
        assert calls == 3
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_groq_timeout_is_normalized() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        provider = GroqProvider(Settings(groq_api_key="test", groq_max_retries=0), client)
        with pytest.raises(LLMTimeoutError):
            await provider.generate("system", "user")
    finally:
        await client.aclose()
