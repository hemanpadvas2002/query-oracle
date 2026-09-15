"""
Google Gemini provider — gemini-flash / gemini-pro / gemini-thinking.

Requires: pip install google-generativeai
"""
from __future__ import annotations
from ..models import EffortLevel, ProviderType, QueryTier, RouterConfig
from .base import BaseProvider, CompletionResult

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore


class GeminiProvider(BaseProvider):
    def __init__(self, config: RouterConfig, api_key: str | None = None):
        if genai is None:
            raise ImportError(
                "Install the Gemini SDK: pip install google-generativeai"
            )
        import os
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise ValueError(
                "Set GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable."
            )
        genai.configure(api_key=key)
        self.config = config

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GEMINI

    def complete(self, query: str, tier: QueryTier, effort: EffortLevel) -> CompletionResult:
        model_id   = self.config.gemini_models[tier]
        max_tokens = self.config.max_tokens_map[tier]

        model = genai.GenerativeModel(model_id)
        generation_config = genai.types.GenerationConfig(max_output_tokens=max_tokens)

        response = model.generate_content(query, generation_config=generation_config)
        text = response.text or ""

        usage = getattr(response, "usage_metadata", None)
        return CompletionResult(
            content=text,
            model_used=model_id,
            provider=ProviderType.GEMINI,
            extended_thinking_used=("thinking" in model_id),
            input_tokens=getattr(usage, "prompt_token_count", 0),
            output_tokens=getattr(usage, "candidates_token_count", 0),
        )
