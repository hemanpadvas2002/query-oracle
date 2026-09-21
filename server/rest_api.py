"""
FastAPI REST server — universal integration point.

Works with any tool that can make an HTTP POST request:
  Cursor, VS Code extension, Codex, n8n, scripts, anything.

Run:
    pip install "query-oracle[server]"
    uvicorn server.rest_api:app --port 8000 --reload

Endpoints:
    POST /route        — route a query, returns full metadata  (auth required)
    POST /classify     — classify only, no LLM execution       (auth required)
    GET  /health       — liveness check                        (open)

Security:
    Set QUERY_ORACLE_API_KEY in the environment to enable Bearer token auth.
    When unset, the server logs a startup warning and runs open (dev-only mode).

Rate limiting:
    _RATE_CACHE is in-process memory (see below). For multi-worker or
    multi-instance deployments, replace it with a shared store such as Redis
    (e.g. via redis-py or aioredis) so limits are enforced across all workers.
    A single uvicorn worker with --workers 1 is safe with the current approach.
"""
from __future__ import annotations
import logging
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    raise ImportError("pip install fastapi uvicorn")

from llm_router import QueryRouter, RouterConfig, ProviderType
from llm_router.providers import AnthropicProvider, OpenAIProvider, GeminiProvider

logger = logging.getLogger(__name__)

# ── Security config ───────────────────────────────────────────────────────────

_API_KEY = os.environ.get("QUERY_ORACLE_API_KEY", "")

_CORS_ORIGINS_RAW = os.environ.get("CORS_ORIGINS", "")
_CORS_ORIGINS = (
    [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]
    if _CORS_ORIGINS_RAW
    else ["*"]
)

# ── Rate limiting (in-memory, per client IP, /route only) ─────────────────────
# WARNING: _RATE_CACHE lives in the uvicorn process's heap. It resets on every
# restart and is NOT shared across multiple workers or instances. Running with
# --workers N > 1 or deploying multiple containers means each worker enforces
# its own independent limit, so a client can multiply their effective rate by N.
# For production multi-worker deployments, replace this with a Redis-backed
# counter (e.g. redis-py INCR + EXPIRE) shared across all workers.

_RATE_CACHE: dict[str, deque] = {}
_RATE_LIMIT  = 30
_RATE_WINDOW = 60  # seconds


def _check_rate_limit(client_ip: str) -> None:
    now          = datetime.utcnow()
    window_start = now - timedelta(seconds=_RATE_WINDOW)
    if client_ip not in _RATE_CACHE:
        _RATE_CACHE[client_ip] = deque()
    ts = _RATE_CACHE[client_ip]
    while ts and ts[0] < window_start:
        ts.popleft()
    if len(ts) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded — 30 requests/minute.")
    ts.append(now)


# ── Auth dependency ───────────────────────────────────────────────────────────

async def _verify_token(authorization: str = Header(default="")) -> None:
    if not _API_KEY:
        return  # no key configured → open access (dev mode)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="query-oracle",
    description="Automatic model + effort routing based on query classification.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    if not _API_KEY:
        logger.warning(
            "QUERY_ORACLE_API_KEY is not set — the API is open to anyone. "
            "Set the variable before exposing this server publicly."
        )
    if _CORS_ORIGINS == ["*"]:
        logger.warning(
            "CORS_ORIGINS is not set — the server accepts requests from any origin. "
            "This is fine for local development but insecure for public-facing deployments. "
            "Set CORS_ORIGINS to a comma-separated list of allowed origins, e.g.: "
            "CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com"
        )


# ── Module-scope router cache (PERF 11) ───────────────────────────────────────
# Keyed by (provider_name, key_fingerprint) so per-request BYOK callers each
# get their own cached router without mixing keys between callers.
# key_fingerprint is None when falling back to the server-side env var.

_ROUTER_CACHE: dict[tuple[str, str | None], QueryRouter] = {}


def _get_router(provider_name: str, api_key: str | None = None) -> QueryRouter:
    name = provider_name.lower()
    # Use last 8 chars as a cheap fingerprint — enough to separate callers,
    # never logged, never stored in full.
    fingerprint = api_key[-8:] if api_key else None
    cache_key = (name, fingerprint)
    if cache_key not in _ROUTER_CACHE:
        config = RouterConfig()
        if name == "anthropic":
            provider = AnthropicProvider(config, api_key=api_key)
        elif name == "openai":
            provider = OpenAIProvider(config, api_key=api_key)
        elif name == "gemini":
            provider = GeminiProvider(config, api_key=api_key)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_name}")
        _ROUTER_CACHE[cache_key] = QueryRouter(config=config, provider=provider)
    return _ROUTER_CACHE[cache_key]


# ── Request / Response schemas ────────────────────────────────────────────────

class RouteRequest(BaseModel):
    query:            str
    provider:         Optional[str] = "anthropic"
    provider_api_key: Optional[str] = None  # BYOK: overrides server env var for this request


class ClassifyRequest(BaseModel):
    query:            str
    provider_api_key: Optional[str] = None  # BYOK: key for the classifier LLM call


class ClassificationOut(BaseModel):
    tier:                    str
    effort:                  str
    facts_ratio:             float
    judgment_ratio:          float
    confidence:              float
    reasoning:               str
    classifier_input_tokens:  int   = 0
    classifier_output_tokens: int   = 0
    classifier_cost_usd:      float = 0.0


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
    cost_usd:               float
    total_cost_usd:         float = 0.0
    classification:         ClassificationOut


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/classify", response_model=ClassificationOut, dependencies=[Depends(_verify_token)])
def classify(req: ClassifyRequest):
    router = _get_router("anthropic", api_key=req.provider_api_key)
    result = router.classifier.classify(req.query)
    return ClassificationOut(
        tier=result.tier.value,
        effort=result.effort.value,
        facts_ratio=result.facts_ratio,
        judgment_ratio=result.judgment_ratio,
        confidence=result.confidence,
        reasoning=result.reasoning,
        classifier_input_tokens=result.classifier_input_tokens,
        classifier_output_tokens=result.classifier_output_tokens,
        classifier_cost_usd=result.classifier_cost_usd,
    )


@app.post("/route", response_model=RouteResponse, dependencies=[Depends(_verify_token)])
def route(req: RouteRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    router = _get_router(req.provider or "anthropic", api_key=req.provider_api_key)
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
        cost_usd=r.cost_usd,
        total_cost_usd=r.total_cost_usd,
        classification=ClassificationOut(
            tier=r.classification.tier.value,
            effort=r.classification.effort.value,
            facts_ratio=r.classification.facts_ratio,
            judgment_ratio=r.classification.judgment_ratio,
            confidence=r.classification.confidence,
            reasoning=r.classification.reasoning,
            classifier_input_tokens=r.classification.classifier_input_tokens,
            classifier_output_tokens=r.classification.classifier_output_tokens,
            classifier_cost_usd=r.classification.classifier_cost_usd,
        ),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
