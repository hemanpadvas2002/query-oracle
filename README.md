# query-oracle

> Automatic LLM routing — the right model, the right effort, zero manual selection.

[![CI](https://github.com/hemanpadvas2002/query-oracle/actions/workflows/ci.yml/badge.svg)](https://github.com/hemanpadvas2002/query-oracle/actions/workflows/ci.yml)
[![Live](https://img.shields.io/badge/API-live%20on%20Railway-brightgreen)](https://query-oracle-production.up.railway.app/health)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

---

## Live demo

> **Illustrative** — actual output will vary by provider, model, and query.

```python
from llm_router import QueryRouter

r = QueryRouter().route("Design a fault-tolerant event streaming architecture.")
print(f"tier={r.tier.value}  model={r.model_used}  thinking={r.extended_thinking_used}")
print(f"cost=${r.cost_usd:.5f}  total=${r.total_cost_usd:.5f}  latency={r.latency_ms:.0f}ms")
print(r.classification.reasoning)
```

---

## What it does

query-oracle sits in front of your LLM calls and automatically decides which model deserves the query. Factual lookups go to Haiku or GPT-4o-mini in under a second; open-ended design problems get routed to Opus with extended thinking or o1 with high reasoning effort. The classification itself costs a fraction of a cent and the routing decision is logged so you can fine-tune a local DistilBERT classifier later — eventually dropping the classification API cost to zero.

It ships as a Python library, a live REST API, a Claude Code MCP plugin, a VS Code / Cursor extension, an OpenAI Custom GPT Action, and a reusable GitHub Actions workflow. Pick whichever integration fits your stack.

---

## Quick install — pick your platform

### Python library

```bash
pip install "query-oracle"
```

With optional extras:

```bash
pip install "query-oracle[server]"     # FastAPI REST server
pip install "query-oracle[mcp]"        # Claude Code / Desktop MCP plugin
pip install "query-oracle[openai]"     # OpenAI provider
pip install "query-oracle[gemini]"     # Gemini provider
pip install "query-oracle[all]"        # everything
```

### Claude Code / Claude Desktop (MCP)

```bash
pip install "query-oracle[mcp]"
claude mcp add query-oracle -- query-oracle-mcp
```

Then in any Claude conversation:

```
route "Design a real-time fraud detection pipeline."
classify "What is the capital of France?"
```

Or add to `~/.claude/claude_desktop_config.json` manually:

```json
{
  "mcpServers": {
    "query-oracle": {
      "command": "query-oracle-mcp",
      "env": { "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}
```

---

### ChatGPT — Custom GPT Action

Paste this URL into **GPT builder → Configure → Actions → Import from URL**:

```
https://query-oracle-production.up.railway.app/openapi.json
```

The server is live — no setup required. See [`openai-plugin/README.md`](openai-plugin/README.md) for how to self-host and add authentication.

---

### Cursor / VS Code Extension

The extension starts the REST server automatically — no manual uvicorn command.

```bash
cd vscode-extension
npm install
npm run package                               # → query-oracle-1.0.0.vsix
code --install-extension query-oracle-1.0.0.vsix
```

Press `Cmd/Ctrl+Shift+L` to open the query input. Responses appear in the **LLM Query Router** output panel with tier, model, latency, and cost.

---

### GitHub Copilot / Codex

Copy `.github/copilot-instructions.md` into your own repo's `.github/` folder. Copilot will read it automatically in VS Code and JetBrains and stop suggesting hard-coded model names.

For GitHub Actions / Copilot Workspace tasks:

```yaml
jobs:
  design:
    uses: hemanpadvas2002/query-oracle/.github/workflows/copilot-router.yml@main
    with:
      query: "Design a zero-downtime database migration strategy."
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    # outputs: response, tier, model_used, cost_usd
```

---

## How routing works

| Tier | When | Anthropic | OpenAI | Gemini |
|---|---|---|---|---|
| `fast` | Factual lookups, maths, news, nutrition | claude-haiku-4-5 | gpt-4o-mini | gemini-1.5-flash |
| `balanced` | Analysis, explanations, moderate reasoning | claude-sonnet-4-5 | gpt-4o | gemini-1.5-pro |
| `deep` | Strategy, design, ethics, complex ideation | claude-opus-4-5 + thinking | o1 (high) | gemini-2.0-flash-thinking |

The classifier sends the query to a small model (Haiku by default) with a structured prompt that returns `tier`, `effort`, `facts_ratio`, `judgment_ratio`, `confidence`, and a one-sentence `reasoning`. Every result is logged to `logs/classifications.jsonl` — this passively builds the labelled dataset for local DistilBERT fine-tuning.

---

## Response fields

```python
RouterResponse(
    content      = "...",
    tier         = QueryTier.DEEP,
    effort       = EffortLevel.HIGH,
    provider     = ProviderType.ANTHROPIC,
    model_used   = "claude-opus-4-5",
    extended_thinking_used = True,
    input_tokens  = 312,
    output_tokens = 891,
    latency_ms   = 3241.4,
    cost_usd     = 0.02184,   # completion cost only
    total_cost_usd = 0.02188, # completion + classifier cost
    classification = ClassificationResult(
        tier           = QueryTier.DEEP,
        effort         = EffortLevel.HIGH,
        facts_ratio    = 0.12,
        judgment_ratio = 0.88,
        confidence     = 0.94,
        reasoning      = "Complex distributed systems design — strategy tier warranted",
        classifier_input_tokens  = 85,
        classifier_output_tokens = 47,
        classifier_cost_usd      = 0.0000456,
    ),
)
```

---

## Live REST API

**Base URL:** `https://query-oracle-production.up.railway.app`

```bash
# Health check (no auth required)
curl https://query-oracle-production.up.railway.app/health
# {"status":"ok"}

# Classify only (auth required when QUERY_ORACLE_API_KEY is set)
curl -s -X POST https://query-oracle-production.up.railway.app/classify \
  -H "Authorization: Bearer $QUERY_ORACLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "How many calories in a banana?"}' | jq .

# Route and get a full response
curl -s -X POST https://query-oracle-production.up.railway.app/route \
  -H "Authorization: Bearer $QUERY_ORACLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain backpressure in reactive systems.", "provider": "anthropic"}' \
  | jq '{tier, model_used, cost_usd, total_cost_usd, latency_ms}'
```

Interactive docs: [`/docs`](https://query-oracle-production.up.railway.app/docs)

---

## Securing your deployment

By default the server runs in open mode (dev-only). Before exposing it publicly:

**1. Set an API key**

```bash
export QUERY_ORACLE_API_KEY="your-secret-key"
```

All requests to `/route` and `/classify` then require:

```
Authorization: Bearer your-secret-key
```

The `/health` endpoint stays open. The server logs a warning at startup if no key is set.

**2. Restrict CORS origins**

```bash
export CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
```

When unset, CORS defaults to `*` (any origin). Set it to your specific domains in production.

**3. Rate limiting**

The `/route` endpoint enforces 30 requests per minute per client IP in-process. For heavier traffic, put an API gateway (e.g. Nginx, Cloudflare, Railway gateway) in front.

**Railway environment variables:**

```
QUERY_ORACLE_API_KEY   → your secret key
ANTHROPIC_API_KEY      → sk-ant-...
OPENAI_API_KEY         → sk-...   (optional)
GEMINI_API_KEY         → AIza...  (optional)
CORS_ORIGINS           → https://yourdomain.com
```

---

## Train your own classifier (coming soon)

Once `logs/classifications.jsonl` accumulates ~500 entries, run `python training/train.py --data training/data/queries.csv` to fine-tune a local DistilBERT model. Swap it in with `QueryRouter(classifier=DistilBERTClassifier("training/query-classifier-final"))` and classification drops to ~10 ms with zero API cost.

---

## Contributing

Open an issue or PR — the codebase is intentionally small. Adding a new provider means subclassing `BaseProvider` and implementing one method; the routing logic, classifier, and all integrations stay unchanged.

---

## Licence

MIT — see [LICENSE](LICENSE).
