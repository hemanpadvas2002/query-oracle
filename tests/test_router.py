"""Unit tests for QueryRouter — cost tracking and async interface (no API calls)."""
import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch

from llm_router.models import (
    QueryTier, EffortLevel, ProviderType, RouterConfig,
    ClassificationResult, estimate_cost, MODEL_PRICING,
)
from llm_router.router import QueryRouter
from llm_router.providers.base import CompletionResult


# ── helpers ──────────────────────────────────────────────────────────────────

def make_classification(
    tier=QueryTier.FAST,
    classifier_cost_usd: float = 0.0,
) -> ClassificationResult:
    effort_map = {
        QueryTier.FAST: EffortLevel.LOW,
        QueryTier.BALANCED: EffortLevel.MEDIUM,
        QueryTier.DEEP: EffortLevel.HIGH,
    }
    return ClassificationResult(
        tier=tier, effort=effort_map[tier],
        facts_ratio=0.8, judgment_ratio=0.2,
        confidence=0.95, reasoning="test",
        classifier_cost_usd=classifier_cost_usd,
    )


def make_completion(model="claude-haiku-4-5", in_tok=100, out_tok=50) -> CompletionResult:
    return CompletionResult(
        content="answer", model_used=model, provider=ProviderType.ANTHROPIC,
        extended_thinking_used=False, input_tokens=in_tok, output_tokens=out_tok,
    )


def make_router(tier=QueryTier.FAST, model="claude-haiku-4-5"):
    config = RouterConfig(log_classifications=False)
    mock_clf = MagicMock()
    mock_clf.classify.return_value = make_classification(tier)
    mock_prov = MagicMock()
    mock_prov.complete.return_value = make_completion(model)
    return QueryRouter(config=config, provider=mock_prov, classifier=mock_clf)


# ── cost estimation ───────────────────────────────────────────────────────────

def test_estimate_cost_known_model():
    cost = estimate_cost("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=1_000_000)
    in_rate, out_rate = MODEL_PRICING["claude-haiku-4-5"]
    assert cost == pytest.approx(in_rate + out_rate)


def test_estimate_cost_unknown_model():
    assert estimate_cost("unknown-model-xyz", 999, 999) == 0.0


def test_estimate_cost_zero_tokens():
    assert estimate_cost("gpt-4o", 0, 0) == 0.0


def test_router_response_includes_cost():
    router = make_router()
    resp = router.route("How many calories in an egg?")
    assert resp.cost_usd >= 0.0
    # haiku at 100 in + 50 out tokens  →  (100*0.80 + 50*4.00) / 1_000_000
    expected = (100 * 0.80 + 50 * 4.00) / 1_000_000
    assert resp.cost_usd == pytest.approx(expected)


def test_router_response_cost_zero_for_unknown_model():
    config = RouterConfig(log_classifications=False)
    mock_clf = MagicMock()
    mock_clf.classify.return_value = make_classification()
    mock_prov = MagicMock()
    mock_prov.complete.return_value = make_completion(model="some-future-model")
    router = QueryRouter(config=config, provider=mock_prov, classifier=mock_clf)
    resp = router.route("test")
    assert resp.cost_usd == 0.0


# ── BUG 10 fix: total_cost_usd includes classifier cost ──────────────────────

def test_total_cost_usd_includes_classifier_cost():
    """total_cost_usd must equal completion cost + classifier cost."""
    config = RouterConfig(log_classifications=False)
    clf_cost = 0.000042
    mock_clf = MagicMock()
    mock_clf.classify.return_value = make_classification(classifier_cost_usd=clf_cost)
    mock_prov = MagicMock()
    mock_prov.complete.return_value = make_completion()
    router = QueryRouter(config=config, provider=mock_prov, classifier=mock_clf)
    resp = router.route("test")
    expected_completion = (100 * 0.80 + 50 * 4.00) / 1_000_000
    assert resp.cost_usd == pytest.approx(expected_completion)
    assert resp.total_cost_usd == pytest.approx(expected_completion + clf_cost)


def test_total_cost_usd_zero_classifier():
    """When classifier cost is 0 (e.g. DistilBERT), total equals completion cost."""
    router = make_router()
    resp = router.route("test")
    assert resp.total_cost_usd == pytest.approx(resp.cost_usd)


# ── async interface ───────────────────────────────────────────────────────────

def test_async_route_returns_same_as_sync():
    router = make_router()
    sync_resp  = router.route("test query")
    async_resp = asyncio.run(router.async_route("test query"))
    assert async_resp.tier        == sync_resp.tier
    assert async_resp.model_used  == sync_resp.model_used
    assert async_resp.content     == sync_resp.content


def test_async_route_runs_concurrently():
    """Two concurrent async_route calls both complete successfully."""
    router = make_router()

    async def run_two():
        r1, r2 = await asyncio.gather(
            router.async_route("first"),
            router.async_route("second"),
        )
        return r1, r2

    r1, r2 = asyncio.run(run_two())
    assert r1.content == "answer"
    assert r2.content == "answer"
