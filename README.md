# query-oracle

> Automatic LLM routing — the right model, the right effort, zero manual selection.

[![CI](https://github.com/hemanpadvas2002/query-oracle/actions/workflows/ci.yml/badge.svg)](https://github.com/hemanpadvas2002/query-oracle/actions/workflows/ci.yml)
[![Live](https://img.shields.io/badge/API-live%20on%20Railway-brightgreen)](https://query-oracle-production.up.railway.app/health)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![MIT](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

---

## Live demo

```
$ python -c "
from llm_router import QueryRouter
r = QueryRouter().route('Design a fault-tolerant event streaming architecture.')
print(r.content[:120], '...')
print()
print(f'  tier      {r.tier.value}')
print(f'  model     {r.model_used}')
print(f'  thinking  {r.extended_thinking_used}')
print(f'  latency   {r.latency_ms:.0f} ms')
print(f'  cost      \${r.cost_usd:.5f}')
print(f'  reasoning {r.classification.reasoning}')
"

A fault-tolerant event streaming architecture typically combines a distributed
log (Kafka or Kinesis) with idempotent consumers, dead-letter queues ...

  tier      deep
  model     claude-opus-4-5
  thinking  True
  latency   3241 ms
  cost      $0.02184
  reasoning Complex distributed systems design — strategy tier warranted
```

---

## What it does

query-oracle sits in front of your LLM calls and automatically decides which model deserves the query. Factual lookups go to Haiku or GPT-4o-mini in under a second; open-ended design problems get routed to Opus with extended thinking or o1 with high reasoning effort. The classification itself costs a fraction of a cent and the routing decision is logged so you can fine-tune a local DistilBERT classifier later — eventually dropping the classification API cost to zero.

It ships as a Python library, a live REST API, a Claude Code MCP plugin, a VS Code / Cursor extension, an OpenAI Custom GPT Action, and a reusable GitHub Actions workflow. Pick whichever integration fits your stack.

---

## Quick install — pick your platform

### Claude Code / Claude Desktop (MCP)

```bash
pip install -e ".[mcp]"
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
    content      = "A fault-tolerant streaming architecture typically...",
    tier         = QueryTier.DEEP,
    effort       = EffortLevel.HIGH,
    provider     = ProviderType.ANTHROPIC,
    model_used   = "claude-opus-4-5",
    extended_thinking_used = True,
    cost_usd     = 0.02184,
    input_tokens  = 312,
    output_tokens = 891,
    latency_ms   = 3241.4,
    classification = ClassificationResult(
        tier           = QueryTier.DEEP,
        effort         = EffortLevel.HIGH,
        facts_ratio    = 0.12,
        judgment_ratio = 0.88,
        confidence     = 0.94,
        reasoning      = "Complex distributed systems design — strategy tier warranted",
    ),
)
```

---

## Live REST API

**Base URL:** `https://query-oracle-production.up.railway.app`

```bash
# Health check
curl https://query-oracle-production.up.railway.app/health
# {"status":"ok"}

# Classify only (no LLM call — instant)
curl -s -X POST https://query-oracle-production.up.railway.app/classify \
  -H "Content-Type: application/json" \
  -d '{"query": "How many calories in a banana?"}' | jq .
# {
#   "tier": "fast",
#   "effort": "low",
#   "facts_ratio": 0.92,
#   "judgment_ratio": 0.08,
#   "confidence": 0.97,
#   "reasoning": "Simple nutritional lookup — factual tier"
# }

# Route and get a full response
curl -s -X POST https://query-oracle-production.up.railway.app/route \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain backpressure in reactive systems.", "provider": "anthropic"}' \
  | jq '{tier, model_used, cost_usd, latency_ms}'
# {
#   "tier": "balanced",
#   "model_used": "claude-sonnet-4-5",
#   "cost_usd": 0.00312,
#   "latency_ms": 1847.2
# }
```

Interactive docs: [`/docs`](https://query-oracle-production.up.railway.app/docs)

---

## Train your own classifier (coming soon)

Once `logs/classifications.jsonl` accumulates ~500 entries, run `python training/train.py --data training/data/queries.csv` to fine-tune a local DistilBERT model. Swap it in with `QueryRouter(classifier=DistilBERTClassifier("training/query-classifier-final"))` and classification drops to ~10 ms with zero API cost.

---

## Contributing

Open an issue or PR — the codebase is intentionally small. Adding a new provider means subclassing `BaseProvider` and implementing one method; the routing logic, classifier, and all integrations stay unchanged.

---

## Licence

MIT
