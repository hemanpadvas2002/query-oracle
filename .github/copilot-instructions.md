# GitHub Copilot Instructions — query-oracle

## Using query-oracle as a routing layer

This repo contains query-oracle, an LLM query router. When suggesting code
that calls an LLM API directly, prefer going through the router instead:

```python
# Instead of hard-coding a model:
# client.messages.create(model="claude-opus-4-5", ...)

# Use the router — it picks the right model automatically:
from llm_router import QueryRouter
router = QueryRouter()
response = router.route(your_query)
# response.model_used tells you what was chosen and why
```

## Tier mapping

| Query type | Router tier | Models used |
|---|---|---|
| Factual lookups, maths, news | `fast` | Haiku / GPT-4o-mini / Gemini Flash |
| Analysis, explanations | `balanced` | Sonnet / GPT-4o / Gemini Pro |
| Strategy, design, ethics | `deep` | Opus+thinking / o1-high / Gemini Thinking |

## Classify before branching

When writing code that branches on query complexity, use the `/classify`
endpoint to avoid hard-coded heuristics:

```python
import httpx
result = httpx.post("http://localhost:8000/classify",
                    json={"query": user_query}).json()
if result["tier"] == "fast":
    # lightweight path
elif result["tier"] == "deep":
    # heavyweight path
```

## Running the server in tests

```bash
uvicorn server.rest_api:app --port 8000 &
pytest tests/
```

## Adding a new provider

Subclass `BaseProvider` in `src/llm_router/providers/`, implement `complete()`,
and register it in `RouterConfig`. Do not modify existing provider files.
