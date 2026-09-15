"""Anthropic provider — Haiku / Sonnet / Opus with optional extended thinking."""
from __future__ import annotations
import anthropic
from ..models import EffortLevel, ProviderType, QueryTier, RouterConfig
from .base import BaseProvider, CompletionResult


class AnthropicProvider(BaseProvider):
    def __init__(self, config: RouterConfig, api_key: str | None = None):
        self.config = config
        self.client = anthropic.Anthropic(api_key=api_key)  # falls back to env var

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.ANTHROPIC

    def complete(self, query: str, tier: QueryTier, effort: EffortLevel) -> CompletionResult:
        model      = self.config.anthropic_models[tier]
        thinking   = self.config.extended_thinking_map[tier]
        budget     = self.config.thinking_budget_map[tier]
        max_tokens = self.config.max_tokens_map[tier]

        if thinking and budget > 0:
            return self._with_thinking(query, model, budget, max_tokens)
        return self._standard(query, model, max_tokens)

    def _standard(self, query: str, model: str, max_tokens: int) -> CompletionResult:
        r = self.client.messages.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": query}],
        )
        text = "".join(b.text for b in r.content if hasattr(b, "text"))
        return CompletionResult(
            content=text, model_used=model, provider=ProviderType.ANTHROPIC,
            extended_thinking_used=False,
            input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens,
        )

    def _with_thinking(self, query: str, model: str, budget: int, max_tokens: int) -> CompletionResult:
        r = self.client.messages.create(
            model=model, max_tokens=max_tokens,
            thinking={"type": "enabled", "budget_tokens": budget},
            messages=[{"role": "user", "content": query}],
        )
        text = "".join(b.text for b in r.content if b.type == "text")
        return CompletionResult(
            content=text, model_used=model, provider=ProviderType.ANTHROPIC,
            extended_thinking_used=True,
            input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens,
        )
