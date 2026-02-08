"""LLM client wrapper — supports OpenAI and Anthropic."""

import structlog

from docere.config import settings

logger = structlog.get_logger()


class ClaudeClient:
    """Provider-agnostic LLM client.

    Supports OpenAI (gpt-4o-mini, gpt-4o) and Anthropic (Claude Sonnet/Opus).
    Keeps the ClaudeClient name for backward compatibility.
    """

    def __init__(self) -> None:
        self.provider = settings.llm_provider

        if self.provider == "openai":
            import openai
            self.openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            self.default_model = settings.openai_default_model
            logger.info("LLM client initialized", provider="openai", model=self.default_model)
        else:
            import anthropic
            self.anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            self.default_model = settings.default_model
            logger.info("LLM client initialized", provider="anthropic", model=self.default_model)

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a chat message and return the response text."""
        if self.provider == "openai":
            return await self._chat_openai(system_prompt, messages, model, max_tokens, temperature)
        else:
            return await self._chat_anthropic(system_prompt, messages, model, max_tokens, temperature)

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
