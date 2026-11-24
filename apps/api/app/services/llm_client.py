"""Small LLM client interface so reliability providers can swap vendors or use fakes in tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol


class LLMUnavailableError(RuntimeError):
    """The LLM call failed, was refused, or could not be made."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    model: str

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        """Return the model's text. With json_schema, the text must be JSON matching it."""
        ...

    async def aclose(self) -> None:
        ...


Effort = Literal["low", "medium", "high", "max"]


class AnthropicLLMClient:
    """LLMClient backed by the Anthropic Messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        effort: Effort = "low",
        max_tokens: int = 16_000,
    ):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self.model = model
        self._effort = effort
        self._max_tokens = max_tokens

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        # `temperature` is deliberately not sent: current Claude models (Opus 4.7 and later)
        # reject sampling parameters with a 400 and always sample at the default, which
        # already varies between calls. Other LLMClient implementations may honour it.
        output_config: dict[str, Any] = {"effort": self._effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config=output_config,
            )
        except self._anthropic.APIError as error:
            # Timeouts, connection failures and every HTTP status end the same way for the
            # caller (the signal becomes `unavailable`); the class name is kept for logs.
            raise LLMUnavailableError(type(error).__name__) from error
        if response.stop_reason == "refusal":
            raise LLMUnavailableError("stop_reason=refusal")
        if json_schema is not None and response.stop_reason == "max_tokens":
            raise LLMUnavailableError("stop_reason=max_tokens")
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResult(text, response.usage.input_tokens, response.usage.output_tokens)

    async def aclose(self) -> None:
        await self._client.close()
