# llm-query-router

Automatic LLM model and effort-level routing based on query classification. Instead of manually picking Haiku vs Sonnet vs Opus (or GPT-4o-mini vs GPT-4o vs o1, or Gemini Flash vs Pro vs Thinking), the router reads your query, classifies it on a facts-to-judgment spectrum, and dispatches it to the right model at the right effort level — automatically.

```
User Query
    ↓
Classifier (small model or local DistilBERT)
    ↓  tier: fast | balanced | deep
Router
    ↓  selects provider + model + effort + extended thinking
Haiku  /  GPT-4o-mini  /  Gemini Flash        ← FAST
Sonnet /  GPT-4o       /  Gemini Pro           ← BALANCED
Opus   /  o1           /  Gemini Thinking      ← DEEP
    ↓
Response + full routing metadata
```

Works as a Python library, a REST API, a Claude Code / Claude Desktop MCP plugin, and a VS Code / Cursor extension.

---

## Routing logic

| Tier | When | Anthropic | OpenAI | Gemini |
|------|------|-----------|--------|--------|
| `fast` | Factual lookups, news, maths, nutrition | claude-haiku-4-5 | gpt-4o-mini | gemini-1.5-flash |
| `balanced` | Analysis, explanations, moderate reasoning | claude-sonnet-4-5 | gpt-4o | gemini-1.5-pro |
| `deep` | Ideation, strategy, ethics, complex design | claude-opus-4-5 + thinking | o1 (high reasoning) | gemini-2.0-flash-thinking |

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/llm-query-router.git
cd llm-query-router
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add the API key(s) for the provider(s) you want
```

You only need **one** provider key to get started.

---

## 1. Python library

```python
from src.llm_router import QueryRouter

# Default: Anthropic provider, reads ANTHROPIC_API_KEY
router = QueryRouter()
r = router.route("How many calories are in a boiled egg?")

print(r.content)     # answer
print(r.tier)        # QueryTier.FAST
print(r.model_used)  # claude-haiku-4-5
print(r.latency_ms)  # ~800ms
```

```python
# Use OpenAI instead
from src.llm_router import QueryRouter, RouterConfig
from src.llm_router.providers import OpenAIProvider

config = RouterConfig()
router = QueryRouter(config=config, provider=OpenAIProvider(config))
r = router.route("Design an intent-driven AI OS for non-technical users.")
# → tier=DEEP, model=o1, reasoning_effort=high
```

```python
# Use Gemini
from src.llm_router.providers import GeminiProvider
router = QueryRouter(provider=GeminiProvider(config))
```

---

## 2. REST API server (universal — works with any tool)

```bash
uvicorn server.rest_api:app --port 8000 --reload
```

```bash
# Route a query
curl -X POST http://localhost:8000/route \
  -H "Content-Type: application/json" \
  -d '{"query": "Design an AI product strategy.", "provider": "anthropic"}'

# Classify only (no LLM call)
curl -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d '{"query": "How many calories in a banana?"}'

# Swagger UI
open http://localhost:8000/docs
```

---

## 3. Claude Code / Claude Desktop — MCP Plugin

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "llm-query-router": {
      "command": "python",
      "args": ["/absolute/path/to/llm-query-router/server/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "OPENAI_API_KEY":    "sk-...",
        "GEMINI_API_KEY":    "AIza..."
      }
    }
  }
}
```

Restart Claude Desktop / Claude Code. Then use:

```
@llm-query-router route "Design an intent-driven AI OS"
@llm-query-router classify "How many calories in a banana?"
```

The router automatically picks the right model. You don't choose — it chooses.

---

## 4. VS Code / Cursor Extension

The extension sends queries to the local REST API and displays routed responses in an output panel.

**Setup:**
1. Start the REST server: `uvicorn server.rest_api:app --port 8000`
2. Open `vscode-extension/` in VS Code
3. Press `F5` to launch the extension in a new Extension Development Host window
4. Press `Cmd/Ctrl+Shift+L` to ask a question

**Commands (Command Palette):**
- `LLM Router: Ask (auto-route)` — type a query, get routed response
- `LLM Router: Ask with selected text` — highlight code/text, send to router
- `LLM Router: Classify query` — see routing decision without LLM call

**Settings** (`settings.json`):
```json
{
  "llmRouter.apiUrl": "http://localhost:8000",
  "llmRouter.defaultProvider": "anthropic",
  "llmRouter.showRoutingMetadata": true
}
```

**Build a .vsix for permanent install:**
```bash
cd vscode-extension
npm install
npm install -g @vscode/vsce
vsce package
code --install-extension llm-query-router-1.0.0.vsix
```

---

## 5. Codex / GitHub Copilot

Use the REST API as a backend. In any Copilot extension or GitHub Actions workflow:

```bash
# Classify before deciding which model to call in your pipeline
curl -s -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$USER_QUERY\"}" | jq .tier
```

---

## Response object

```python
RouterResponse(
    content:                str,    # model's answer
    tier:                   QueryTier,       # fast | balanced | deep
    effort:                 EffortLevel,     # low | medium | high
    provider:               ProviderType,    # anthropic | openai | gemini
    model_used:             str,
    extended_thinking_used: bool,
    classification: ClassificationResult(
        tier, effort,
        facts_ratio,    # 0.0 = pure judgment → 1.0 = pure facts
        judgment_ratio,
        confidence,
        reasoning,      # one-line explanation (logged for dataset)
    ),
    input_tokens:  int,
    output_tokens: int,
    latency_ms:    float,
)
```

---

## Switching to a local DistilBERT classifier (zero API cost)

Once you have labelled training data, fine-tune DistilBERT and swap the classifier. The routing logic and providers are unchanged.

**Train:**
```bash
pip install transformers datasets torch scikit-learn optimum onnxruntime
python training/train.py --data training/data/queries.csv
```

Dataset format (`training/data/queries.csv`):
```csv
query,label
"How many calories in a banana?",fast
"Explain TCP vs UDP.",balanced
"Design an AI OS architecture.",deep
```

**Use the trained model:**
```python
from src.llm_router import QueryRouter, DistilBERTClassifier

clf    = DistilBERTClassifier("training/query-classifier-final", use_onnx=True)
router = QueryRouter(classifier=clf)
# → Classification now runs locally in ~10ms, zero API cost
```

---

## Adding a new provider

Subclass `BaseProvider` and implement one method:

```python
from src.llm_router.providers.base import BaseProvider, CompletionResult
from src.llm_router.models import QueryTier, EffortLevel, ProviderType

class MistralProvider(BaseProvider):
    @property
    def provider_type(self): return ProviderType("mistral")

    def complete(self, query, tier, effort) -> CompletionResult:
        model = {"fast": "mistral-small", "balanced": "mistral-medium", "deep": "mistral-large"}[tier.value]
        # ... call API ...
        return CompletionResult(content=..., model_used=model, ...)

router = QueryRouter(provider=MistralProvider(config))
```

---

## Custom model config

```python
from src.llm_router import RouterConfig, QueryTier

config = RouterConfig(
    anthropic_models={
        QueryTier.FAST:     "claude-haiku-4-5",
        QueryTier.BALANCED: "claude-sonnet-4-5",
        QueryTier.DEEP:     "claude-sonnet-4-5",  # Sonnet for DEEP (cheaper)
    },
    thinking_budget_map={QueryTier.DEEP: 12000},
)
```

---

## Project structure

```
llm-query-router/
├── src/llm_router/
│   ├── models.py              ← Data types (QueryTier, RouterConfig, RouterResponse…)
│   ├── classifier.py          ← PromptClassifier + DistilBERTClassifier
│   ├── router.py              ← QueryRouter (main entry point)
│   └── providers/
│       ├── base.py            ← BaseProvider interface
│       ├── anthropic_provider.py
│       ├── openai_provider.py
│       └── gemini_provider.py
├── server/
│   ├── rest_api.py            ← FastAPI server (universal integration)
│   └── mcp_server.py         ← Claude Code / Claude Desktop MCP plugin
├── vscode-extension/          ← VS Code / Cursor extension (TypeScript)
│   ├── package.json
│   └── src/extension.ts
├── training/
│   ├── train.py              ← DistilBERT fine-tuning script
│   └── data/                 ← Put your queries.csv here
├── examples/
│   ├── basic_usage.py
│   └── multi_provider.py
└── logs/                     ← Auto-generated classification log (JSONL)
```

---

## Roadmap

- [ ] Fine-tuned DistilBERT classifier (local, zero API cost, ~10ms)
- [ ] ONNX export for plugin bundling
- [ ] Mistral provider
- [ ] Streaming responses
- [ ] Async interface
- [ ] Cost tracker (tokens × price per model)
- [ ] UCB1 bandit for adaptive routing from user feedback

---

## Push to GitHub

```bash
cd llm-query-router
git init
git add .
git commit -m "Initial commit: llm-query-router"
git remote add origin https://github.com/YOUR_USERNAME/llm-query-router.git
git branch -M main
git push -u origin main
```

---

## Licence

MIT
