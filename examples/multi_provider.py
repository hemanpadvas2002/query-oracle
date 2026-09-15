"""
Multi-provider example — route the same query through all three providers.

export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AIza...
python examples/multi_provider.py
"""
from src.llm_router import QueryRouter, RouterConfig
from src.llm_router.providers import AnthropicProvider, OpenAIProvider, GeminiProvider

config = RouterConfig()

providers = {
    "Anthropic": AnthropicProvider(config),
    "OpenAI":    OpenAIProvider(config),
    "Gemini":    GeminiProvider(config),
}

query = "Design the architecture for an intent-driven AI OS for non-technical users."

for name, provider in providers.items():
    try:
        router = QueryRouter(config=config, provider=provider)
        r = router.route(query)
        print(f"\n{'='*60}")
        print(f"Provider: {name}  |  Model: {r.model_used}  |  Tier: {r.tier.value}")
        print(f"Tokens: {r.input_tokens}in / {r.output_tokens}out  |  {r.latency_ms:.0f}ms")
        print(f"\n{r.content[:400]}...")
    except Exception as e:
        print(f"\n[{name}] Skipped — {e}")
