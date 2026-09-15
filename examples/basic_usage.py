"""
Basic usage — Anthropic provider (default).

export ANTHROPIC_API_KEY=sk-ant-...
python examples/basic_usage.py
"""
from src.llm_router import QueryRouter

router = QueryRouter()

queries = [
    "How many calories are in a boiled egg?",                                          # → FAST
    "Who won the 2024 US presidential election?",                                      # → FAST
    "Explain the difference between supervised and unsupervised learning.",             # → BALANCED
    "I'm building a cognitive OS for non-technical users. What are the three biggest " # → DEEP
    "UX risks I should design around?",
]

for q in queries:
    r = router.route(q)
    print(f"\nQ: {q}")
    print(f"  Tier={r.tier.value}  Model={r.model_used}  Thinking={r.extended_thinking_used}  {r.latency_ms:.0f}ms")
    print(f"  Classifier: {r.classification.reasoning}")
    print(f"  Answer: {r.content[:180]}...")
