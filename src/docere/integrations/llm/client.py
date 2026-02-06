"""Anthropic Claude API client wrapper."""

import anthropic
import structlog

from docere.config import settings

logger = structlog.get_logger()


class ClaudeClient:
    """Wrapper around the Anthropic Claude API."""

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.default_model = settings.default_model

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat message and return the response text."""
        response = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text

    async def judge(
        self,
        prompt: str,
        max_tokens: int = 500,
    ) -> str:
        """Use Claude as a judge/evaluator (low temperature for consistency)."""
        return await self.chat(
            system_prompt=prompt,
            messages=[{"role": "user", "content": "Evaluate the interaction above."}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
