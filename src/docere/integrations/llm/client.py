"""LLM client wrapper — supports OpenAI and Anthropic with retry and circuit breaker."""

from collections.abc import AsyncIterator
from functools import partial

import structlog

from docere.config import settings
from docere.core.resilience import CircuitBreaker, retry_async

logger = structlog.get_logger()

# Shared circuit breaker per provider (module-level so it persists across requests)
_llm_breaker = CircuitBreaker(service="llm", failure_threshold=5, recovery_timeout=30.0)

# Exceptions worth retrying (transient errors)
_RETRYABLE_OPENAI: tuple[type[Exception], ...] = ()
_RETRYABLE_ANTHROPIC: tuple[type[Exception], ...] = ()

try:
    import openai

    _RETRYABLE_OPENAI = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.RateLimitError,
        openai.InternalServerError,
    )
except ImportError:
    pass

try:
    import anthropic

    _RETRYABLE_ANTHROPIC = (
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.RateLimitError,
        anthropic.InternalServerError,
    )
except ImportError:
    pass


class ClaudeClient:
    """Provider-agnostic LLM client with retry and circuit breaker.

    Supports OpenAI (gpt-4o-mini, gpt-4o) and Anthropic (Claude Sonnet/Opus).
    Keeps the ClaudeClient name for backward compatibility.
    """

    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.breaker = _llm_breaker

        if self.provider == "openai":
            import openai

            self.openai_client = openai.AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=30.0,
            )
            self.default_model = settings.openai_default_model
            self._retryable = _RETRYABLE_OPENAI
            logger.info("LLM client initialized", provider="openai", model=self.default_model)
        else:
            import anthropic

            self.anthropic_client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=30.0,
            )
            self.default_model = settings.default_model
            self._retryable = _RETRYABLE_ANTHROPIC
            logger.info("LLM client initialized", provider="anthropic", model=self.default_model)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat message with retry and circuit breaker protection."""
        if self.provider == "openai":
            call = partial(
                self._chat_openai, system_prompt, messages, model, max_tokens, temperature
            )
        else:
            call = partial(
                self._chat_anthropic, system_prompt, messages, model, max_tokens, temperature
            )

        return await self.breaker.call(
            lambda: retry_async(
                call,
                max_retries=3,
                base_delay=0.5,
                max_delay=10.0,
                retryable=self._retryable or (Exception,),
            )
        )

    async def _chat_openai(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await self.openai_client.chat.completions.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=openai_messages,
        )
        return response.choices[0].message.content

    async def _chat_anthropic(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        response = await self.anthropic_client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    async def stream(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive from the LLM.

        Circuit breaker wraps the connection setup (not individual chunks).
        No retry on mid-stream failures — the SSE endpoint handles reconnection.
        """
        if self.provider == "openai":
            gen = self._stream_openai(system_prompt, messages, model, max_tokens, temperature)
        else:
            gen = self._stream_anthropic(system_prompt, messages, model, max_tokens, temperature)

        # Circuit breaker guards the initial connection.
        # We pull the first chunk inside breaker.call() to detect connection errors,
        # then yield the rest outside (mid-stream errors surface naturally).
        first_chunk_holder: list[str] = []

        async def _connect() -> None:
            async for chunk in gen:
                first_chunk_holder.append(chunk)
                break  # got the first chunk, connection is healthy

        await self.breaker.call(_connect)

        # Yield the first chunk we already received
        if first_chunk_holder:
            yield first_chunk_holder[0]

        # Yield remaining chunks (outside circuit breaker)
        async for chunk in gen:
            yield chunk

    async def _stream_openai(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        openai_messages = [{"role": "system", "content": system_prompt}] + messages
        response = await self.openai_client.chat.completions.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=openai_messages,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def _stream_anthropic(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        async with self.anthropic_client.messages.stream(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def judge(
        self,
        prompt: str,
        max_tokens: int = 500,
    ) -> str:
        """Use LLM as a judge/evaluator (low temperature for consistency)."""
        return await self.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Evaluate the interaction above."}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
