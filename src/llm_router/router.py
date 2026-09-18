"""
QueryRouter — the single entry point.

from llm_router import QueryRouter
from llm_router.providers import OpenAIProvider

router = QueryRouter(provider=OpenAIProvider(config))
response = router.route("Design an intent-driven AI OS for non-technical users.")
print(response.content, response.tier, response.model_used)
"""
from __future__ import annotations
import asyncio
import time

from .classifier import BaseClassifier, PromptClassifier
from .models import RouterConfig, RouterResponse, estimate_cost
from .providers.base import BaseProvider


class QueryRouter:
    """
    Classify → Route → Execute.

    Parameters
    ----------
    config     : RouterConfig, optional  — override model IDs, budgets, etc.
    provider   : BaseProvider            — which LLM backend to execute on
                 (AnthropicProvider / OpenAIProvider / GeminiProvider)
    classifier : BaseClassifier, optional — swap in DistilBERTClassifier once trained
    """

    def __init__(
        self,
        config:     RouterConfig  | None = None,
        provider:   BaseProvider  | None = None,
        classifier: BaseClassifier| None = None,
    ):
        self.config = config or RouterConfig()

        # Default provider: Anthropic (reads ANTHROPIC_API_KEY from env)
        if provider is None:
            from .providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider(self.config)
        self.provider = provider

        # Default classifier: prompt-based (uses same provider as classifier_provider in config)
        self.classifier = classifier or PromptClassifier(self.config)

    def route(self, query: str) -> RouterResponse:
        t0 = time.monotonic()

        classification = self.classifier.classify(query)
        completion     = self.provider.complete(
            query, tier=classification.tier, effort=classification.effort
        )

        cost_usd = estimate_cost(
            completion.model_used, completion.input_tokens, completion.output_tokens
        )
        return RouterResponse(
            content=completion.content,
            tier=classification.tier,
            effort=classification.effort,
            provider=completion.provider,
            model_used=completion.model_used,
            extended_thinking_used=completion.extended_thinking_used,
            classification=classification,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            latency_ms=(time.monotonic() - t0) * 1000,
            cost_usd=cost_usd,
            total_cost_usd=cost_usd + classification.classifier_cost_usd,
        )

    async def async_route(self, query: str) -> RouterResponse:
        """Non-blocking version of route() — runs the synchronous call in a thread pool."""
        return await asyncio.to_thread(self.route, query)
