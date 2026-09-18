"""
Core data models for llm-query-router.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class QueryTier(str, Enum):
    FAST     = "fast"      # Factual, simple, low latency
    BALANCED = "balanced"  # Moderate reasoning
    DEEP     = "deep"      # Heavy ideation, judgment, creativity


class EffortLevel(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class ProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI    = "openai"
    GEMINI    = "gemini"


# Pricing per 1 M tokens (input, output) in USD — update as providers change rates.
# Source: provider pricing pages as of mid-2025.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-haiku-4-5":   (0.80,   4.00),
    "claude-sonnet-4-5":  (3.00,  15.00),
    "claude-opus-4-5":    (15.00, 75.00),
    # OpenAI
    "gpt-4o-mini":        (0.15,   0.60),
    "gpt-4o":             (2.50,  10.00),
    "o1":                 (15.00, 60.00),
    # Gemini
    "gemini-1.5-flash":              (0.075,  0.30),
    "gemini-1.5-pro":                (1.25,   5.00),
    "gemini-2.0-flash-thinking-exp": (0.00,   0.00),   # free preview
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for a single call."""
    if model not in MODEL_PRICING:
        return 0.0
    in_rate, out_rate = MODEL_PRICING[model]
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


@dataclass
class ClassificationResult:
    tier:           QueryTier
    effort:         EffortLevel
    facts_ratio:    float   # 0.0 = pure judgment → 1.0 = pure facts
    judgment_ratio: float
    reasoning:      str
    confidence:     float


@dataclass
class RouterConfig:
    """
    All routing behaviour is driven from here.
    Swap model IDs, enable thinking, change token budgets —
    without touching provider or classifier code.
    """

    # ── Anthropic model IDs ──────────────────────────────────────────────
    anthropic_models: dict[QueryTier, str] = field(default_factory=lambda: {
        QueryTier.FAST:     "claude-haiku-4-5",
        QueryTier.BALANCED: "claude-sonnet-4-5",
        QueryTier.DEEP:     "claude-opus-4-5",
    })

    # ── OpenAI model IDs ─────────────────────────────────────────────────
    openai_models: dict[QueryTier, str] = field(default_factory=lambda: {
        QueryTier.FAST:     "gpt-4o-mini",
        QueryTier.BALANCED: "gpt-4o",
        QueryTier.DEEP:     "o1",
    })

    # ── Gemini model IDs ─────────────────────────────────────────────────
    gemini_models: dict[QueryTier, str] = field(default_factory=lambda: {
        QueryTier.FAST:     "gemini-1.5-flash",
        QueryTier.BALANCED: "gemini-1.5-pro",
        QueryTier.DEEP:     "gemini-2.0-flash-thinking-exp",
    })

    # ── Extended thinking (Anthropic only) ───────────────────────────────
    extended_thinking_map: dict[QueryTier, bool] = field(default_factory=lambda: {
        QueryTier.FAST:     False,
        QueryTier.BALANCED: False,
        QueryTier.DEEP:     True,
    })
    thinking_budget_map: dict[QueryTier, int] = field(default_factory=lambda: {
        QueryTier.FAST:     0,
        QueryTier.BALANCED: 0,
        QueryTier.DEEP:     8000,
    })

    # ── Reasoning effort (OpenAI o-series) ───────────────────────────────
    openai_reasoning_effort: dict[QueryTier, Optional[str]] = field(default_factory=lambda: {
        QueryTier.FAST:     None,
        QueryTier.BALANCED: None,
        QueryTier.DEEP:     "high",
    })

    # ── Max output tokens ────────────────────────────────────────────────
    max_tokens_map: dict[QueryTier, int] = field(default_factory=lambda: {
        QueryTier.FAST:     1024,
        QueryTier.BALANCED: 4096,
        QueryTier.DEEP:     8192,
    })

    # ── Classifier settings ──────────────────────────────────────────────
    classifier_provider: ProviderType = ProviderType.ANTHROPIC
    classifier_model:    str          = "claude-haiku-4-5"

    # ── Logging (builds your fine-tuning dataset passively) ─────────────
    log_classifications: bool = True
    log_path:            str  = "logs/classifications.jsonl"


@dataclass
class RouterResponse:
    content:                str
    tier:                   QueryTier
    effort:                 EffortLevel
    provider:               ProviderType
    model_used:             str
    extended_thinking_used: bool
    classification:         ClassificationResult
    input_tokens:           int   = 0
    output_tokens:          int   = 0
    latency_ms:             float = 0.0
    cost_usd:               float = 0.0
