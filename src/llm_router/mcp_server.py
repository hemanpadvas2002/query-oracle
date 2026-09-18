"""
MCP server — package-level module.

Installed entry point: query-oracle-mcp
  (runs via: python -m llm_router.mcp_server  OR  query-oracle-mcp)

Claude Code / Claude Desktop config (~/.claude/claude_desktop_config.json):

  {
    "mcpServers": {
      "query-oracle": {
        "command": "query-oracle-mcp",
        "env": {
          "ANTHROPIC_API_KEY": "sk-ant-...",
          "OPENAI_API_KEY":    "sk-...",
          "GEMINI_API_KEY":    "AIza..."
        }
      }
    }
  }

Or via uvx (no install needed):
  "command": "uvx",
  "args": ["--from", "llm-query-router[mcp]", "query-oracle-mcp"]
"""
from __future__ import annotations

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server import FastMCP  # type: ignore[no-redef]
    except ImportError:
        raise ImportError("Install the MCP SDK: pip install 'llm-query-router[mcp]'")

from .models import RouterConfig
from .router import QueryRouter
from .providers import AnthropicProvider, OpenAIProvider, GeminiProvider

mcp = FastMCP("query-oracle")


def _provider(name: str, config: RouterConfig):
    n = name.lower()
    if n == "openai":
        return OpenAIProvider(config)
    if n == "gemini":
        return GeminiProvider(config)
    return AnthropicProvider(config)


@mcp.tool()
def route(query: str, provider: str = "anthropic") -> str:
    """
    Route a query to the optimal LLM model automatically.

    Classifies the query on a facts-to-judgment spectrum and dispatches it to:
    - FAST  (Haiku / GPT-4o-mini / Gemini Flash)   for factual lookups
    - BALANCED (Sonnet / GPT-4o / Gemini Pro)       for analysis
    - DEEP  (Opus+thinking / o1-high / Gemini Thinking) for strategy & design

    Args:
        query:    The user question or task.
        provider: LLM provider — anthropic | openai | gemini  (default: anthropic)
    """
    config = RouterConfig()
    router = QueryRouter(config=config, provider=_provider(provider, config))
    r = router.route(query)
    meta = (
        f"[query-oracle] tier={r.tier.value} | model={r.model_used} | "
        f"thinking={r.extended_thinking_used} | {r.latency_ms:.0f}ms | "
        f"cost=${r.cost_usd:.6f}\n\n"
    )
    return meta + r.content


@mcp.tool()
def classify(query: str) -> str:
    """
    Classify a query without executing it — returns the routing decision only.

    Args:
        query: The query to classify.
    """
    config = RouterConfig()
    router = QueryRouter(config=config)
    c = router.classifier.classify(query)
    return (
        f"Tier:           {c.tier.value}\n"
        f"Effort:         {c.effort.value}\n"
        f"Facts ratio:    {c.facts_ratio:.0%}\n"
        f"Judgment ratio: {c.judgment_ratio:.0%}\n"
        f"Confidence:     {c.confidence:.0%}\n"
        f"Reasoning:      {c.reasoning}"
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
