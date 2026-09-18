# query-oracle — ChatGPT / Custom GPT Action

This folder contains everything needed to expose query-oracle as a **Custom GPT Action** so any ChatGPT user or Custom GPT can automatically route queries to the right model.

---

## How it works

```
User prompt in ChatGPT
       ↓
GPT Action calls POST /route  (or /classify)
       ↓
query-oracle picks  fast | balanced | deep
       ↓
Response + tier + cost_usd returned to GPT
```

---

## Step 1 — Deploy the REST server

You need a publicly reachable URL.  The fastest options:

### Railway (recommended, one-click)
```bash
railway login
railway init
railway add --service web
# Set env vars: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
railway up
# Note the deployment URL, e.g. https://query-oracle-production.up.railway.app
```

### Render / Fly.io / any PaaS
```bash
# Procfile
web: uvicorn server.rest_api:app --host 0.0.0.0 --port $PORT
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e ".[server]"
CMD ["uvicorn", "server.rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Step 2 — Update the manifest and spec

Edit `openapi.yaml`:
```yaml
servers:
  - url: https://YOUR_DEPLOYMENT_URL   # ← replace
```

Edit `ai-plugin.json`:
```json
"url": "https://YOUR_DEPLOYMENT_URL/openapi.yaml"
"logo_url": "https://YOUR_DEPLOYMENT_URL/logo.png"
```

The FastAPI server automatically serves the OpenAPI spec at `/openapi.json`.
Convert or point directly to `openapi.yaml` if your hosting supports static files.

---

## Step 3 — Register as a Custom GPT Action

1. Go to [chat.openai.com](https://chat.openai.com) → **Explore GPTs** → **Create**
2. Click **Configure** → scroll to **Actions** → **Create new action**
3. Paste the contents of `openapi.yaml` into the schema editor
4. Set Authentication to **None** (or add an API key if you want to protect it)
5. Click **Test** on `routeQuery` — enter a sample query and verify a response
6. Save and publish

---

## Endpoints available to the GPT

| Endpoint | Use |
|---|---|
| `POST /route` | Full routed response (most useful) |
| `POST /classify` | Routing decision only — no model call |
| `GET /health` | Liveness check |

---

## GPT system prompt suggestion

Paste this into the Custom GPT's system prompt to make routing automatic:

```
You have access to the query-oracle action.
Before answering any substantive question, call classifyQuery to determine
the complexity tier. For tier=deep questions, call routeQuery instead of
answering yourself — the router will engage the best reasoning model.
For tier=fast questions, you may answer directly if you are confident.
```
