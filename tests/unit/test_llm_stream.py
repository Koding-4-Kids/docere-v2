"""Tests for ClaudeClient.stream() async generator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from docere.core.resilience import CircuitBreaker


class TestClaudeClientStreamAnthropic:
    """Test streaming with the Anthropic provider."""

    async def test_yields_text_chunks(self):
        """stream() should yield each text chunk from Anthropic's text_stream."""
        client = self._make_client(["Hello", " world", "!"])
        chunks = [c async for c in client.stream("sys", [{"role": "user", "content": "hi"}])]
        assert chunks == ["Hello", " world", "!"]

    async def test_empty_stream(self):
        """stream() should handle an empty stream gracefully."""
        client = self._make_client([])
        chunks = [c async for c in client.stream("sys", [{"role": "user", "content": "hi"}])]
        assert chunks == []

    async def test_circuit_breaker_trips_on_connection_error(self):
        """stream() should trip the circuit breaker if the initial connection fails."""
        client = self._make_client([], connection_error=ConnectionError("down"))

        with pytest.raises(ConnectionError, match="down"):
            async for _ in client.stream("sys", [{"role": "user", "content": "hi"}]):
                pass

    async def test_single_chunk_stream(self):
        """stream() should work with a single chunk."""
        client = self._make_client(["only one"])
        chunks = [c async for c in client.stream("sys", [{"role": "user", "content": "hi"}])]
        assert chunks == ["only one"]

    async def test_passes_parameters(self):
        """stream() should forward model, max_tokens, temperature to the provider."""
        client = self._make_client(["ok"])
        _ = [c async for c in client.stream(
            "system prompt",
            [{"role": "user", "content": "test"}],
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.5,
        )]

        # Verify the Anthropic client was called with correct params
        client.anthropic_client.messages.stream.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.5,
            system="system prompt",
            messages=[{"role": "user", "content": "test"}],
        )

    # ── Helper ──

    @staticmethod
    def _make_client(chunks: list[str], connection_error: Exception | None = None):
        """Build a ClaudeClient with a mocked Anthropic streaming backend."""
        from docere.integrations.llm.client import ClaudeClient

        with patch.object(ClaudeClient, "__init__", lambda self: None):
            client = ClaudeClient()

        client.provider = "anthropic"
        client.default_model = "claude-sonnet-4-20250514"
        client.breaker = CircuitBreaker(service="test-llm")
        client._retryable = (ConnectionError,)

        # Build a mock async context manager for messages.stream()
        mock_stream = AsyncMock()

        async def _text_stream_gen():
            if connection_error:
                raise connection_error
            for c in chunks:
                yield c

        mock_stream.text_stream = _text_stream_gen()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_anthropic = MagicMock()
        mock_anthropic.messages.stream = MagicMock(return_value=mock_ctx)
        client.anthropic_client = mock_anthropic

        return client


class TestClaudeClientStreamOpenAI:
    """Test streaming with the OpenAI provider."""

    async def test_yields_text_chunks(self):
        """stream() should yield each text chunk from OpenAI's streamed response."""
        client = self._make_client(["Hi", " there"])
        chunks = [c async for c in client.stream("sys", [{"role": "user", "content": "hi"}])]
        assert chunks == ["Hi", " there"]

    async def test_skips_empty_deltas(self):
        """stream() should skip chunks with no content in delta."""
        client = self._make_client(["Hello", None, " world"])
        chunks = [c async for c in client.stream("sys", [{"role": "user", "content": "hi"}])]
        assert chunks == ["Hello", " world"]

    # ── Helper ──

    @staticmethod
    def _make_client(chunks: list[str | None]):
        """Build a ClaudeClient with a mocked OpenAI streaming backend."""
        from docere.integrations.llm.client import ClaudeClient

        with patch.object(ClaudeClient, "__init__", lambda self: None):
            client = ClaudeClient()

        client.provider = "openai"
        client.default_model = "gpt-4o-mini"
        client.breaker = CircuitBreaker(service="test-llm")
        client._retryable = (ConnectionError,)

        # Build mock OpenAI streamed response
        mock_chunks = []
        for text in chunks:
            chunk = MagicMock()
            delta = MagicMock()
            delta.content = text
            choice = MagicMock()
            choice.delta = delta
            chunk.choices = [choice]
            mock_chunks.append(chunk)

        async def _create(**kwargs):
            for c in mock_chunks:
                yield c

        mock_openai = MagicMock()
        mock_openai.chat.completions.create = _create
        client.openai_client = mock_openai

        return client
