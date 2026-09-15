"""Unit tests for the classifier (no API calls)."""
import json
import pytest
from unittest.mock import MagicMock
from src.llm_router.classifier import PromptClassifier
from src.llm_router.models import RouterConfig, QueryTier, EffortLevel


def clf():
    config = RouterConfig(log_classifications=False)
    client = MagicMock()
    return PromptClassifier(config, client)


def mock_response(data):
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps(data))]
    return m


def test_fast_tier():
    c = clf()
    c._client.messages.create.return_value = mock_response(
        {"tier": "fast", "effort": "low", "facts_ratio": 0.9,
         "judgment_ratio": 0.1, "confidence": 0.95, "reasoning": "Simple lookup."})
    r = c.classify("calories in a banana")
    assert r.tier == QueryTier.FAST
    assert r.effort == EffortLevel.LOW


def test_deep_tier():
    c = clf()
    c._client.messages.create.return_value = mock_response(
        {"tier": "deep", "effort": "high", "facts_ratio": 0.1,
         "judgment_ratio": 0.9, "confidence": 0.88, "reasoning": "Heavy ideation."})
    r = c.classify("Design an AI OS")
    assert r.tier == QueryTier.DEEP


def test_malformed_falls_back():
    c = clf()
    c._client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="not json")])
    r = c.classify("anything")
    assert r.tier == QueryTier.BALANCED
    assert r.confidence == 0.0


def test_markdown_fenced_json():
    c = clf()
    fenced = "```json\n" + json.dumps(
        {"tier": "balanced", "effort": "medium", "facts_ratio": 0.5,
         "judgment_ratio": 0.5, "confidence": 0.7, "reasoning": "Moderate."}
    ) + "\n```"
    c._client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=fenced)])
    r = c.classify("Explain ML")
    assert r.tier == QueryTier.BALANCED
