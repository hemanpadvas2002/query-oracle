# query-oracle

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
Response + full routing metadata (tier, cost_usd, latency_ms, …)
```

Works as a **Python library**, a **REST API**, a **Claude Code / Claude Desktop MCP plugin**, a **VS Code / Cursor extension**, a **ChatGPT / Custom GPT Action**, and a **GitHub Copilot skill**.

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
git clone https://github.com/hemanpadvas2002/query-oracle.git
cd query-oracle
pip install -e .          # core (Anthropic + routing)
pip install -e ".[all]"   # all providers + server + MCP
cp .env.example .env
# Edit .env — add the API key(s) for the provider(s) you want
```

You only need **one** provider key to get started.

---

## 1. Python library

```python
from llm_router import QueryRouter

router = QueryRouter()
r = router.route("How many calories are in a boiled egg?")

print(r.content)      # answer
print(r.tier)         # QueryTier.FAST
print(r.model_used)   # claude-haiku-4-5
print(r.latency_ms)   # ~800ms
print(r.cost_usd)     # ~0.000004
```

```python
# Async interface
import asyncio
from llm_router import QueryRouter

router = QueryRouter()
r = asyncio.run(router.async_route("Design an intent-driven AI OS."))
# Or with gather:
r1, r2 = asyncio.run(asyncio.gather(
    router.async_route("How does TCP work?"),
    router.async_route("Design a fraud detection system."),
))
```

```python
# Use OpenAI instead
from llm_router import QueryRouter, RouterConfig
from llm_router.providers import OpenAIProvider

config = RouterConfig()
router = QueryRouter(config=config, provider=OpenAIProvider(config))
r = router.route("Design an intent-driven AI OS for non-technical users.")
# → tier=DEEP, model=o1, reasoning_effort=high
```

---

## 2. REST API server (universal)

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

### Option A — installed console script (recommended)

```bash
pip install -e ".[mcp]"
claude mcp add query-oracle -- query-oracle-mcp
```

### Option B — direct file path (no install needed)

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "query-oracle": {
      "command": "python",
      "args": ["/absolute/path/to/query-oracle/server/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "OPENAI_API_KEY":    "sk-...",
        "GEMINI_API_KEY":    "AIza..."
      }
    }
  }
}
```

Restart Claude Desktop / Claude Code. Then use in chat:

```
route "Design an intent-driven AI OS"
classify "How many calories in a banana?"
```

The router picks the right model automatically.

---

## 4. VS Code / Cursor Extension

The extension **starts the REST server automatically** on first use — no manual uvicorn command.

### Install from .vsix

```bash
cd vscode-extension
npm install
npm run package          # produces query-oracle-1.0.0.vsix
code --install-extension query-oracle-1.0.0.vsix
```

### Install from Marketplace (once published)

Search for **"Query Oracle"** in the Extensions panel, or:
```
ext install phadvas-industries.query-oracle
```

### Usage

Press `Cmd/Ctrl+Shift+L` to open the input box.  
The extension:
1. Checks if the REST server is running on port 8000
2. If not, spawns it automatically using your configured Python path
3. Routes your query and displays the response in the **LLM Query Router** output panel

### Settings (`settings.json`)

```json
{
  "llmRouter.defaultProvider":      "anthropic",
  "llmRouter.autoStart":            true,
  "llmRouter.pythonPath":           "python",
  "llmRouter.serverPort":           8000,
  "llmRouter.showRoutingMetadata":  true
}
```

### Commands (Command Palette)

| Command | Shortcut |
|---|---|
| `LLM Router: Ask (auto-route)` | `Cmd/Ctrl+Shift+L` |
| `LLM Router: Ask with selected text` | — |
| `LLM Router: Classify query` | — |

### Publish to VS Code Marketplace

Push a tag (`git tag v1.0.0 && git push --tags`) — the `vsce-publish.yml` workflow builds and publishes automatically. Requires a `VSCE_PAT` secret (Azure DevOps personal access token with Marketplace → Manage scope).

---

## 5. ChatGPT / Custom GPT Action

See [`openai-plugin/README.md`](openai-plugin/README.md) for full setup.

Quick summary:
1. Deploy the REST server to a public URL (Railway, Render, Fly.io, Docker)
2. In Custom GPT builder → **Actions** → paste `openai-plugin/openapi.yaml`
3. Update the server URL in the spec
4. Test `routeQuery` and save

---

## 6. GitHub Copilot

### Repository-level instructions

`.github/copilot-instructions.md` tells Copilot to use the router in this repo. Instructions are automatically picked up by GitHub Copilot in supported editors.

### Reusable Copilot skill (GitHub Actions)

Call the router from any workflow or Copilot Workspace task:

```yaml
jobs:
  design:
    uses: hemanpadvas2002/query-oracle/.github/workflows/copilot-router.yml@main
    with:
      query: "Design a fault-tolerant event streaming architecture."
      provider: "anthropic"
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

The workflow outputs `response`, `tier`, `model_used`, and `cost_usd`.

### One-liner in any Copilot pipeline

```bash
TIER=$(curl -s -X POST http://localhost:8000/classify \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$USER_QUERY\"}" | jq -r .tier)

echo "Routing tier: $TIER"
```

---

## Response object

```python
RouterResponse(
    content:                str,         # model's answer
    tier:                   QueryTier,   # fast | balanced | deep
    effort:                 EffortLevel, # low | medium | high
    provider:               ProviderType,
    model_used:             str,
    extended_thinking_used: bool,
    cost_usd:               float,       # estimated cost in USD
    classification: ClassificationResult(
        tier, effort,
        facts_ratio,     # 0.0 = pure judgment → 1.0 = pure facts
        judgment_ratio,
        confidence,
        reasoning,       # one-line explanation
    ),
    input_tokens:  int,
    output_tokens: int,
    latency_ms:    float,
)
```

---

## Switching to a local DistilBERT classifier (zero API cost)

Once you have labelled training data, fine-tune DistilBERT and swap the classifier:

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

```python
from llm_router import QueryRouter, DistilBERTClassifier

clf    = DistilBERTClassifier("training/query-classifier-final", use_onnx=True)
router = QueryRouter(classifier=clf)
# → Classification now runs locally in ~10ms, zero API cost
```

---

## Adding a new provider

```python
from llm_router.providers.base import BaseProvider, CompletionResult
from llm_router.models import QueryTier, EffortLevel, ProviderType

class MistralProvider(BaseProvider):
    @property
    def provider_type(self): return ProviderType("mistral")

    def complete(self, query, tier, effort) -> CompletionResult:
        model = {"fast": "mistral-small", "balanced": "mistral-medium",
                 "deep": "mistral-large"}[tier.value]
        # ... call API ...
        return CompletionResult(content=..., model_used=model, ...)

router = QueryRouter(provider=MistralProvider(config))
```

---

## Custom model config

```python
from llm_router import RouterConfig, QueryTier

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
query-oracle/
├── src/llm_router/
│   ├── models.py              ← QueryTier, RouterConfig, RouterResponse, MODEL_PRICING
│   ├── classifier.py          ← PromptClassifier + DistilBERTClassifier
│   ├── router.py              ← QueryRouter (route + async_route)
│   ├── mcp_server.py          ← MCP server module (console script entry point)
│   └── providers/
│       ├── base.py
│       ├── anthropic_provider.py
│       ├── openai_provider.py
│       └── gemini_provider.py
├── server/
│   ├── rest_api.py            ← FastAPI server (universal integration)
│   └── mcp_server.py         ← Thin shim → delegates to llm_router.mcp_server
├── vscode-extension/          ← VS Code / Cursor extension (TypeScript)
│   ├── package.json
│   ├── .vscodeignore
│   └── src/
│       ├── extension.ts       ← commands + display
│       └── server-manager.ts  ← auto-start/stop the REST server
├── openai-plugin/
│   ├── openapi.yaml           ← OpenAPI 3.1 spec for GPT Actions
│   ├── ai-plugin.json         ← GPT Action manifest
│   └── README.md              ← deploy & register instructions
├── .github/
│   ├── copilot-instructions.md  ← repo-level Copilot guidance
│   └── workflows/
│       ├── ci.yml               ← pytest on push (Python 3.10–3.12)
│       ├── vsce-publish.yml     ← publish extension on git tag
│       └── copilot-router.yml   ← reusable Copilot skill workflow
├── training/
│   ├── train.py               ← DistilBERT fine-tuning + ONNX export
│   └── data/                  ← put queries.csv here
├── examples/
│   ├── basic_usage.py
│   └── multi_provider.py
└── logs/                      ← auto-generated classification log (JSONL)
```

---

## Roadmap

- [x] GitHub Actions CI (pytest, Python 3.10–3.12)
- [x] Cost tracker (`cost_usd` on every response)
- [x] Async interface (`async_route`)
- [x] MCP console script (`query-oracle-mcp`)
- [x] VS Code extension auto-start server
- [x] VS Code Marketplace publish workflow
- [x] ChatGPT / Custom GPT Action (OpenAPI spec)
- [x] GitHub Copilot instructions + reusable skill workflow
- [ ] Fine-tuned DistilBERT classifier (local, ~10ms)
- [ ] ONNX export for extension bundling
- [ ] Mistral provider
- [ ] Streaming responses
- [ ] UCB1 bandit for adaptive routing from user feedback

---

## Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: query-oracle"
git remote add origin https://github.com/hemanpadvas2002/query-oracle.git
git branch -M main
git push -u origin main
```

---

## Licence

MIT
