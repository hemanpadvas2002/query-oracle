"""
Query classifier.

Two backends, same interface:
  PromptClassifier   — calls a small LLM (default, works immediately)
  DistilBERTClassifier — loads a fine-tuned local model (zero API cost,
                         ~10ms inference; requires a trained model directory)

Swap backends by passing a different classifier instance to QueryRouter.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from abc import ABC, abstractmethod

from .models import ClassificationResult, EffortLevel, QueryTier, RouterConfig

# ─────────────────────────────────────────────────────────────────────────────
# Abstract base
# ─────────────────────────────────────────────────────────────────────────────

class BaseClassifier(ABC):
    @abstractmethod
    def classify(self, query: str) -> ClassificationResult: ...


# ─────────────────────────────────────────────────────────────────────────────
# Option A: Prompt-based (works out of the box, any provider)
# ─────────────────────────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """\
You are a query classification engine. Analyse the user query and return JSON:

{{
  "tier":           "fast" | "balanced" | "deep",
  "effort":         "low"  | "medium"   | "high",
  "facts_ratio":    <float 0.0-1.0>,
  "judgment_ratio": <float 0.0-1.0>,
  "confidence":     <float 0.0-1.0>,
  "reasoning":      "<one sentence>"
}}

Rules:
- facts_ratio + judgment_ratio = 1.0
- fast     -> factual lookups, news, nutrition, simple maths
- balanced -> moderate analysis, explanations with nuance
- deep     -> ideation, strategy, ethics, complex design
- effort follows tier by default but may be raised one level for unusually nuanced queries.

Return ONLY the JSON. No text outside it.

Query: {query}"""


class PromptClassifier(BaseClassifier):
    """
    Classifies queries via a prompt call to a small LLM.
    Works immediately with any API key. Logs every result for future fine-tuning.
    """

    def __init__(self, config: RouterConfig, client=None):
        self.config = config
        self._client = client
        if config.log_classifications:
            Path(config.log_path).parent.mkdir(parents=True, exist_ok=True)

    def classify(self, query: str) -> ClassificationResult:
        raw    = self._call_model(query)
        result = self._parse(raw)
        if self.config.log_classifications:
            self._log(query, result)
        return result

    def _call_model(self, query: str) -> str:
        from .models import ProviderType
        provider = self.config.classifier_provider
        prompt   = CLASSIFICATION_PROMPT.format(query=query)

        if provider == ProviderType.ANTHROPIC:
            import anthropic
            client = self._client or anthropic.Anthropic()
            r = client.messages.create(
                model=self.config.classifier_model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return r.content[0].text.strip()

        elif provider == ProviderType.OPENAI:
            from openai import OpenAI
            client = self._client or OpenAI()
            r = client.chat.completions.create(
                model=self.config.classifier_model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return r.choices[0].message.content.strip()

        elif provider == ProviderType.GEMINI:
            import google.generativeai as genai
            model = genai.GenerativeModel(self.config.classifier_model)
            return model.generate_content(prompt).text.strip()

        raise ValueError(f"Unknown classifier provider: {provider}")

    def _parse(self, raw: str) -> ClassificationResult:
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            return ClassificationResult(
                tier=QueryTier.BALANCED, effort=EffortLevel.MEDIUM,
                facts_ratio=0.5, judgment_ratio=0.5,
                reasoning=f"Parse error — defaulted. Raw: {raw[:80]}",
                confidence=0.0,
            )
        return ClassificationResult(
            tier=QueryTier(d.get("tier", "balanced")),
            effort=EffortLevel(d.get("effort", "medium")),
            facts_ratio=float(d.get("facts_ratio", 0.5)),
            judgment_ratio=float(d.get("judgment_ratio", 0.5)),
            reasoning=d.get("reasoning", ""),
            confidence=float(d.get("confidence", 0.8)),
        )

    def _log(self, query: str, result: ClassificationResult) -> None:
        entry = {
            "timestamp":      time.time(),
            "query":          query,
            "tier":           result.tier.value,
            "effort":         result.effort.value,
            "facts_ratio":    result.facts_ratio,
            "judgment_ratio": result.judgment_ratio,
            "confidence":     result.confidence,
            "reasoning":      result.reasoning,
        }
        with open(self.config.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Option B: Fine-tuned DistilBERT (zero API cost, ~10ms, runs locally)
# ─────────────────────────────────────────────────────────────────────────────

LABEL2TIER = {0: QueryTier.FAST, 1: QueryTier.BALANCED, 2: QueryTier.DEEP}
TIER2EFFORT = {
    QueryTier.FAST:     EffortLevel.LOW,
    QueryTier.BALANCED: EffortLevel.MEDIUM,
    QueryTier.DEEP:     EffortLevel.HIGH,
}


class DistilBERTClassifier(BaseClassifier):
    """
    Zero-cost local classifier using a fine-tuned DistilBERT model.

    Usage:
        clf = DistilBERTClassifier("./training/query-classifier-final")
        router = QueryRouter(classifier=clf)

    Train your model first using the scripts in /training/.
    Requires: pip install transformers torch  (or onnxruntime for ONNX)
    """

    def __init__(self, model_dir: str, use_onnx: bool = False):
        self.model_dir = model_dir
        self.use_onnx  = use_onnx
        self._model    = None
        self._tokenizer = None
        self._ort_session = None
        self._load()

    def _load(self):
        if self.use_onnx:
            self._load_onnx()
        else:
            self._load_pytorch()

    def _load_pytorch(self):
        try:
            from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
            import torch
            self._tokenizer = DistilBertTokenizerFast.from_pretrained(self.model_dir)
            self._model = DistilBertForSequenceClassification.from_pretrained(self.model_dir)
            self._model.eval()
            self._torch = torch
        except ImportError:
            raise ImportError(
                "Install pytorch + transformers: pip install transformers torch"
            )

    def _load_onnx(self):
        try:
            import onnxruntime as ort
            from transformers import DistilBertTokenizerFast
            self._tokenizer = DistilBertTokenizerFast.from_pretrained(self.model_dir)
            onnx_path = f"{self.model_dir}/model.onnx"
            self._ort_session = ort.InferenceSession(onnx_path)
        except ImportError:
            raise ImportError(
                "Install onnxruntime: pip install onnxruntime"
            )

    def classify(self, query: str) -> ClassificationResult:
        if self.use_onnx:
            return self._classify_onnx(query)
        return self._classify_pytorch(query)

    def _classify_pytorch(self, query: str) -> ClassificationResult:
        import torch
        inputs = self._tokenizer(
            query, return_tensors="pt", truncation=True,
            padding="max_length", max_length=128,
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs     = torch.softmax(logits, dim=-1)[0]
        label_id  = int(probs.argmax())
        confidence = float(probs[label_id])
        tier = LABEL2TIER[label_id]
        return ClassificationResult(
            tier=tier, effort=TIER2EFFORT[tier],
            facts_ratio=float(probs[0]),
            judgment_ratio=float(probs[2]),
            reasoning="DistilBERT local classifier",
            confidence=confidence,
        )

    def _classify_onnx(self, query: str) -> ClassificationResult:
        import numpy as np
        inputs = self._tokenizer(
            query, return_tensors="np", truncation=True,
            padding="max_length", max_length=128,
        )
        logits = self._ort_session.run(
            None,
            {"input_ids": inputs["input_ids"], "attention_mask": inputs["attention_mask"]},
        )[0]
        probs     = np.exp(logits) / np.exp(logits).sum()
        label_id  = int(probs.argmax())
        confidence = float(probs[0][label_id])
        tier = LABEL2TIER[label_id]
        return ClassificationResult(
            tier=tier, effort=TIER2EFFORT[tier],
            facts_ratio=float(probs[0][0]),
            judgment_ratio=float(probs[0][2]),
            reasoning="DistilBERT ONNX local classifier",
            confidence=confidence,
        )
