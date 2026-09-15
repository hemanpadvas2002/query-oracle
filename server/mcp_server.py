"""
MCP Server — integrates llm-query-router as a Claude Code / Claude Desktop plugin.

Installation (Claude Code):
    Add to ~/.claude/claude_desktop_config.json:

    {
      "mcpServers": {
        "llm-query-router": {
          "command": "python",
          "args": ["/path/to/llm-query-router/server/mcp_server.py"],
          "env": {
            "ANTHROPIC_API_KEY": "sk-ant-...",
            "OPENAI_API_KEY":    "sk-...",
            "GEMINI_API_KEY":    "AIza..."
          }
        }
      }
    }

Then in Claude Code: @llm-query-router route "your query here"

Requires: pip install mcp
"""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from mcp.server import FastMCP
except ImportError:
    raise ImportError("pip install mcp")

from src.llm_router import QueryRouter, RouterConfig
from src.llm_router.providers import AnthropicProvider, OpenAIProvider, GeminiProvider

mcp = FastMCP("llm-query-router")


def _get_provider(provider_name: str, config: RouterConfig):
    name = provider_name.lower()
    if name == "openai":
        return OpenAIProvider(config)
    if name == "gemini":
        return GeminiProvider(config)
    return AnthropicProvider(config)   # default


@mcp.tool()
def route(query: str, provider: str = "anthropic") -> str:
    """
    Route a query to the optimal LLM model based on its content.
    Automatically picks Haiku/GPT-4o-mini/Gemini Flash for simple queries
    and Opus/o1/Gemini Thinking for complex ideation.

    Args:
        query:    The user's question or task.
        provider: Which LLM provider to use — anthropic | openai | gemini (default: anthropic)

    Returns:
        The model's response with routing metadata prepended.
    """
    config   = RouterConfig()
    prov     = _get_provider(provider, config)
    router   = QueryRouter(config=config, provider=prov)
    r        = router.route(query)

    meta = (
        f"[Router] tier={r.tier.value} | model={r.model_used} | "
        f"thinking={r.extended_thinking_used} | {r.latency_ms:.0f}ms\n\n"
    )
    return meta + r.content


@mcp.tool()
def classify(query: str) -> str:
    """
    Classify a query without executing it.
    Returns the tier, effort level, and reasoning.

    Args:
        query: The query to classify.
    """
    config = RouterConfig()
    router = QueryRouter(config=config)
    c      = router.classifier.classify(query)
    return (
        f"Tier:           {c.tier.value}\n"
        f"Effort:         {c.effort.value}\n"
        f"Facts ratio:    {c.facts_ratio:.0%}\n"
        f"Judgment ratio: {c.judgment_ratio:.0%}\n"
        f"Confidence:     {c.confidence:.0%}\n"
        f"Reasoning:      {c.reasoning}"
    )


if __name__ == "__main__":
    mcp.run()
