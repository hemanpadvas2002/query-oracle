"""Abstract provider interface — implement this to add any LLM backend."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from ..models import EffortLevel, ProviderType, QueryTier


@dataclass
class CompletionResult:
    content:                str
    model_used:             str
    provider:               ProviderType
    extended_thinking_used: bool
    input_tokens:           int
    output_tokens:          int


class BaseProvider(ABC):
    @abstractmethod
    def complete(self, query: str, tier: QueryTier, effort: EffortLevel) -> CompletionResult: ...

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType: ...
