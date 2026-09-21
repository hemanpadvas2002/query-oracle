# Contributing to query-oracle

Thank you for taking the time to contribute. The codebase is intentionally
small — adding a new provider means subclassing `BaseProvider` and implementing
one method; the routing logic, classifier, and all integrations stay unchanged.

## Reporting issues

Open an issue at https://github.com/hemanpadvas2002/query-oracle/issues.
Please include:

- Python version and OS
- The query or code that triggered the problem
- The full traceback if applicable
- Which provider you were using (anthropic / openai / gemini)

## Submitting a pull request

1. Fork the repo and create a branch from `main`.
2. Make your change. Keep it focused — one fix or feature per PR.
3. Run the test suite and confirm it passes:
   ```bash
   pip install -e ".[server,mcp,openai,gemini]"
   pytest
   ```
4. Open a PR against `main` with a clear description of what changed and why.

## Adding a new provider

Subclass `BaseProvider` in `src/llm_router/providers/` and implement:

```python
def complete(self, query: str, tier: QueryTier, effort: EffortLevel) -> CompletionResult:
    ...
```

Register the provider in `src/llm_router/providers/__init__.py` and add it to
the provider selection logic in `server/rest_api.py` and `src/llm_router/mcp_server.py`.

## Code style

- Python 3.10+, type-annotated
- No comments explaining *what* the code does — only *why* when the reason is non-obvious
- No new dependencies unless strictly necessary

## Code of Conduct

By participating you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
