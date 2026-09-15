"""
OpenAI provider — gpt-4o-mini / gpt-4o / o1.

Requires: pip install openai
"""
from __future__ import annotations
from ..models import EffortLevel, ProviderType, QueryTier, RouterConfig
from .base import BaseProvider, CompletionResult

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


class OpenAIProvider(BaseProvider):
    def __init__(self, config: RouterConfig, api_key: str | None = None):
        if OpenAI is None:
            raise ImportError("Install the openai package: pip install openai")
        self.config = config
        self.client = OpenAI(api_key=api_key)  # falls back to OPENAI_API_KEY

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    def complete(self, query: str, tier: QueryTier, effort: EffortLevel) -> CompletionResult:
        model      = self.config.openai_models[tier]
        max_tokens = self.config.max_tokens_map[tier]
        reasoning  = self.config.openai_reasoning_effort.get(tier)

        kwargs: dict = {
            "model": model,
            "messages": [{"role": "user", "content": query}],
        }

        # o-series models use max_completion_tokens and support reasoning_effort
        if model.startswith("o"):
            kwargs["max_completion_tokens"] = max_tokens
            if reasoning:
                kwargs["reasoning_effort"] = reasoning
        else:
            kwargs["max_tokens"] = max_tokens

        r = self.client.chat.completions.create(**kwargs)
        text = r.choices[0].message.content or ""

        return CompletionResult(
            content=text,
            model_used=model,
            provider=ProviderType.OPENAI,
            extended_thinking_used=(model.startswith("o") and reasoning == "high"),
            input_tokens=r.usage.prompt_tokens if r.usage else 0,
            output_tokens=r.usage.completion_tokens if r.usage else 0,
        )
