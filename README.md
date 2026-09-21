# query-oracle

> Automatic LLM routing — the right model, the right effort, zero manual selection.

[![PyPI](https://img.shields.io/pypi/v/query-oracle)](https://pypi.org/project/query-oracle/)
[![CI](https://github.com/hemanpadvas2002/query-oracle/actions/workflows/ci.yml/badge.svg)](https://github.com/hemanpadvas2002/query-oracle/actions/workflows/ci.yml)
[![API: self-host](https://img.shields.io/badge/API-self--host-blue)](https://query-oracle-production.up.railway.app/health)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

---

## Live demo

**Prerequisites:** set your API key before running — either `export ANTHROPIC_API_KEY="sk-ant-..."` in your shell, or add it to a `.env` file in your project root.

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

It ships as a Python library, a REST server you self-host, and an MCP plugin for tools that support the Model Context Protocol natively. The level of integration varies — see the table below.

---

## Compatibility

> **Billing note:** query-oracle makes its own API calls using your provider key. It is not a proxy for your coding tool's core loop, and it does **not** reduce that tool's subscription usage. Every `route` or `classify` call is billed separately to your `ANTHROPIC_API_KEY` (or whichever provider you configure).

| Tool | Integration | What it does |
|---|---|---|
| Claude Code | MCP server (built-in) | `route` and `classify` become explicit tool calls; Claude delegates subtasks to the router |
| Google Antigravity | MCP server (built-in) | Same as above — first-class MCP support, identical config block |
| Cursor | VS Code extension (standalone) | Manual query panel (Cmd/Ctrl+Shift+L) using your own API keys; **not** woven into Cursor's native AI chat |
| Codex CLI | None yet | No plugin hook exists; call `/classify` manually via curl in scripts as a workaround |

Run the setup wizard to get the exact steps for your tool:

```bash
pip install query-oracle
query-oracle-init
```

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

## REST API

`/health` is the only endpoint that works without configuration — it just confirms the server is up:

```bash
curl https://query-oracle-production.up.railway.app/health
# {"status":"ok"}
```

`/route` and `/classify` require a running instance with your own provider key set. The Railway deployment above has no `ANTHROPIC_API_KEY`, so those endpoints will error. **Deploy your own instance** (Railway, Render, Docker — see the Procfile) with your keys, then:

```bash
# Classify only (no model call)
curl -s -X POST https://your-instance.up.railway.app/classify \
  -H "Authorization: Bearer $QUERY_ORACLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "How many calories in a banana?"}' | jq .

# Route and get a full response
curl -s -X POST https://your-instance.up.railway.app/route \
  -H "Authorization: Bearer $QUERY_ORACLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain backpressure in reactive systems.", "provider": "anthropic"}' \
  | jq '{tier, model_used, cost_usd, total_cost_usd, latency_ms}'
```

See the [Securing your deployment](#securing-your-deployment) section for the required environment variables. Interactive docs are available at `/docs` on any running instance.

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

## Releasing

Releases are published to PyPI automatically via GitHub Actions when a version tag is pushed.

```bash
# 1. Bump version in pyproject.toml, commit, push
git tag v0.4.0
git push origin v0.4.0

# 2. Go to github.com/hemanpadvas2002/query-oracle → Releases → "Create release from tag"
#    Publishing the GitHub Release triggers .github/workflows/publish.yml
#    which builds and uploads to PyPI via OIDC (no stored token needed).
```

Before the first tag-triggered publish works, register the trusted publisher once at
[pypi.org/manage/project/query-oracle/settings/publishing/](https://pypi.org/manage/project/query-oracle/settings/publishing/)
with owner `hemanpadvas2002`, repo `query-oracle`, workflow `publish.yml`.

---

## Licence

MIT — see [LICENSE](LICENSE).
