"""Unit tests for the classifier (no API calls)."""
import json
import pytest
from unittest.mock import MagicMock
from llm_router.classifier import PromptClassifier
from llm_router.models import RouterConfig, RouterResponse, QueryTier, EffortLevel, ProviderType


def clf():
    config = RouterConfig(log_classifications=False)
    client = MagicMock()
    client.messages.create.return_value = _mock_anthropic_response(
        {"tier": "fast", "effort": "low", "facts_ratio": 0.9,
         "judgment_ratio": 0.1, "confidence": 0.95, "reasoning": "default"}
    )
    return PromptClassifier(config, client)


def _mock_anthropic_response(data):
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps(data))]
    m.usage.input_tokens  = 10
    m.usage.output_tokens = 5
    return m


# ── existing tests ────────────────────────────────────────────────────────────

def test_fast_tier():
    c = clf()
    c._client.messages.create.return_value = _mock_anthropic_response(
        {"tier": "fast", "effort": "low", "facts_ratio": 0.9,
         "judgment_ratio": 0.1, "confidence": 0.95, "reasoning": "Simple lookup."})
    r = c.classify("calories in a banana")
    assert r.tier == QueryTier.FAST
    assert r.effort == EffortLevel.LOW


def test_deep_tier():
    c = clf()
    c._client.messages.create.return_value = _mock_anthropic_response(
        {"tier": "deep", "effort": "high", "facts_ratio": 0.1,
         "judgment_ratio": 0.9, "confidence": 0.88, "reasoning": "Heavy ideation."})
    r = c.classify("Design an AI OS")
    assert r.tier == QueryTier.DEEP


def test_malformed_falls_back():
    c = clf()
    bad = MagicMock()
    bad.content = [MagicMock(text="not json")]
    bad.usage.input_tokens  = 8
    bad.usage.output_tokens = 3
    c._client.messages.create.return_value = bad
    r = c.classify("anything")
    assert r.tier == QueryTier.BALANCED
    assert r.confidence == 0.0


def test_markdown_fenced_json():
    c = clf()
    fenced = "```json\n" + json.dumps(
        {"tier": "balanced", "effort": "medium", "facts_ratio": 0.5,
         "judgment_ratio": 0.5, "confidence": 0.7, "reasoning": "Moderate."}
    ) + "\n```"
    bad = MagicMock()
    bad.content = [MagicMock(text=fenced)]
    bad.usage.input_tokens  = 10
    bad.usage.output_tokens = 5
    c._client.messages.create.return_value = bad
    r = c.classify("Explain ML")
    assert r.tier == QueryTier.BALANCED


# ── BUG 7 fix: enum coercion ──────────────────────────────────────────────────

def test_uppercase_tier_coerced():
    """LLM returning uppercase 'FAST' must not crash — coerces to QueryTier.FAST."""
    c = clf()
    c._client.messages.create.return_value = _mock_anthropic_response(
        {"tier": "FAST", "effort": "LOW", "facts_ratio": 0.9,
         "judgment_ratio": 0.1, "confidence": 0.9, "reasoning": "ok"})
    r = c.classify("quick question")
    assert r.tier == QueryTier.FAST
    assert r.effort == EffortLevel.LOW


def test_nonsense_tier_falls_back_to_balanced():
    """Unrecognised tier value must fall back to BALANCED, not raise ValueError."""
    c = clf()
    c._client.messages.create.return_value = _mock_anthropic_response(
        {"tier": "medium-high", "effort": "medium", "facts_ratio": 0.5,
         "judgment_ratio": 0.5, "confidence": 0.5, "reasoning": "ok"})
    r = c.classify("some query")
    assert r.tier == QueryTier.BALANCED


# ── BUG 9 fix: Gemini uses injected client ────────────────────────────────────

def test_gemini_uses_injected_client():
    """Gemini branch must call self._client.generate_content(), not re-create a model."""
    config = RouterConfig(
        log_classifications=False,
        classifier_provider=ProviderType.GEMINI,
        classifier_model="gemini-1.5-flash",
    )
    mock_client = MagicMock()
    mock_r = MagicMock()
    mock_r.text = json.dumps(
        {"tier": "fast", "effort": "low", "facts_ratio": 0.9,
         "judgment_ratio": 0.1, "confidence": 0.9, "reasoning": "test"}
    )
    mock_r.usage_metadata.prompt_token_count     = 12
    mock_r.usage_metadata.candidates_token_count = 8
    mock_client.generate_content.return_value = mock_r
    c = PromptClassifier(config, mock_client)
    r = c.classify("simple fact")
    mock_client.generate_content.assert_called_once()
    assert r.tier == QueryTier.FAST
    assert r.classifier_input_tokens == 12
    assert r.classifier_output_tokens == 8


# ── CRITICAL 1 fix: RouterConfig.__post_init__ ────────────────────────────────

def test_router_config_post_init_raises_when_budget_equals_max():
    """thinking_budget == max_tokens must raise ValueError."""
    with pytest.raises(ValueError, match="max_tokens_map"):
        RouterConfig(
            thinking_budget_map={QueryTier.FAST: 0, QueryTier.BALANCED: 0, QueryTier.DEEP: 8000},
            max_tokens_map={QueryTier.FAST: 1024, QueryTier.BALANCED: 4096, QueryTier.DEEP: 8000},
        )


def test_router_config_post_init_raises_when_budget_exceeds_max():
    """thinking_budget > max_tokens must raise ValueError."""
    with pytest.raises(ValueError, match="max_tokens_map"):
        RouterConfig(
            thinking_budget_map={QueryTier.FAST: 0, QueryTier.BALANCED: 0, QueryTier.DEEP: 9000},
            max_tokens_map={QueryTier.FAST: 1024, QueryTier.BALANCED: 4096, QueryTier.DEEP: 8000},
        )


def test_router_config_default_deep_is_valid():
    """Default RouterConfig (DEEP max=16000, budget=8000) must not raise."""
    config = RouterConfig()  # should not raise
    assert config.max_tokens_map[QueryTier.DEEP] > config.thinking_budget_map[QueryTier.DEEP]
