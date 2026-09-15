"""
FastAPI REST server — universal integration point.

Works with any tool that can make an HTTP POST request:
  Cursor, VS Code extension, Codex, n8n, scripts, anything.

Run:
    pip install fastapi uvicorn
    uvicorn server.rest_api:app --port 8000 --reload

Endpoints:
    POST /route        — route a query, returns full metadata
    POST /classify     — classify only, no LLM execution
    GET  /health       — liveness check
"""
from __future__ import annotations
import os
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    raise ImportError("pip install fastapi uvicorn")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.llm_router import QueryRouter, RouterConfig, ProviderType
from src.llm_router.providers import AnthropicProvider, OpenAIProvider, GeminiProvider

app = FastAPI(
    title="LLM Query Router",
    description="Automatic model + effort routing based on query classification.",
    version="1.0.0",
)


# ── Request / Response schemas ────────────────────────────────────────────────

class RouteRequest(BaseModel):
    query:    str
    provider: Optional[str] = "anthropic"  # anthropic | openai | gemini


class ClassifyRequest(BaseModel):
    query: str


class ClassificationOut(BaseModel):
    tier:           str
    effort:         str
    facts_ratio:    float
    judgment_ratio: float
    confidence:     float
    reasoning:      str


class RouteResponse(BaseModel):
    content:                str
    tier:                   str
    effort:                 str
    provider:               str
    model_used:             str
    extended_thinking_used: bool
    input_tokens:           int
    output_tokens:          int
    latency_ms:             float
    classification:         ClassificationOut


# ── Provider factory ──────────────────────────────────────────────────────────

def _make_provider(provider_name: str, config: RouterConfig):
    name = provider_name.lower()
    if name == "anthropic":
        return AnthropicProvider(config)
    if name == "openai":
        return OpenAIProvider(config)
    if name == "gemini":
        return GeminiProvider(config)
    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify", response_model=ClassificationOut)
def classify(req: ClassifyRequest):
    config = RouterConfig()
    router = QueryRouter(config=config)
    result = router.classifier.classify(req.query)
    return ClassificationOut(
        tier=result.tier.value,
        effort=result.effort.value,
        facts_ratio=result.facts_ratio,
        judgment_ratio=result.judgment_ratio,
        confidence=result.confidence,
        reasoning=result.reasoning,
    )


@app.post("/route", response_model=RouteResponse)
def route(req: RouteRequest):
    config   = RouterConfig()
    provider = _make_provider(req.provider or "anthropic", config)
    router   = QueryRouter(config=config, provider=provider)

    try:
        r = router.route(req.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return RouteResponse(
        content=r.content,
        tier=r.tier.value,
        effort=r.effort.value,
        provider=r.provider.value,
        model_used=r.model_used,
        extended_thinking_used=r.extended_thinking_used,
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        latency_ms=r.latency_ms,
        classification=ClassificationOut(
            tier=r.classification.tier.value,
            effort=r.classification.effort.value,
            facts_ratio=r.classification.facts_ratio,
            judgment_ratio=r.classification.judgment_ratio,
            confidence=r.classification.confidence,
            reasoning=r.classification.reasoning,
        ),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
