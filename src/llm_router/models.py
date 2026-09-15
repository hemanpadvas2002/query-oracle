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
