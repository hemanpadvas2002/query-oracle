"""
query-oracle setup wizard.

Asks which tool you use and prints the exact steps to wire query-oracle in.
Honest about what is and isn't integrated — no overstatements.

Run:
    python -m llm_router.init
    query-oracle-init
"""
from __future__ import annotations
import json
import os
import platform
import sys
from pathlib import Path

# ── MCP server config block (same shape for any MCP-native tool) ─────────────

_MCP_BLOCK = {
    "mcpServers": {
        "query-oracle": {
            "command": "query-oracle-mcp",
            "env": {
                "ANTHROPIC_API_KEY": "sk-ant-...",
            },
        }
    }
}

_MCP_JSON = json.dumps(_MCP_BLOCK, indent=2)

_ENV_SNIPPET = """\
# .env  (copy to your project root)
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...       # optional — needed for provider=openai
# GEMINI_API_KEY=AIza...      # optional — needed for provider=gemini
"""


def _hr() -> None:
    print("\n" + "─" * 60 + "\n")


def _header() -> None:
    print("\n  query-oracle setup wizard")
    print("  ─────────────────────────")
    print("  Answers are local only — nothing is sent anywhere.\n")


def _prompt_tool() -> str:
    options = [
        ("1", "Claude Code"),
        ("2", "Google Antigravity"),
        ("3", "Cursor"),
        ("4", "Codex CLI"),
        ("5", "None — library only"),
    ]
    print("Which tool do you use?\n")
    for key, label in options:
        print(f"  {key}. {label}")
    print()
    while True:
        choice = input("Enter a number [1-5]: ").strip()
        if choice in {k for k, _ in options}:
            return choice
        print("  Please enter 1, 2, 3, 4, or 5.")


# ── per-tool handlers ─────────────────────────────────────────────────────────

def _claude_code() -> None:
    _hr()
    print("Claude Code — MCP server (first-class support)\n")
    print("1. Install:\n")
    print("   pip install 'query-oracle[mcp]'\n")
    print("2. Register with Claude Code (one command):\n")
    print("   claude mcp add query-oracle -- query-oracle-mcp\n")
    print("   Then set your key in the environment Claude Code runs in:\n")
    print("   export ANTHROPIC_API_KEY=sk-ant-...\n")
    print("3. Or add manually to ~/.claude/claude_desktop_config.json:\n")
    print(_MCP_JSON)
    print()
    print("Once registered, use these tool calls in any Claude conversation:")
    print()
    print('   route "Design a fault-tolerant event streaming architecture."')
    print('   classify "What is the capital of France?"')
    print()
    print("⚠  Billing note: each route/classify call is a SEPARATE API call")
    print("   billed to your ANTHROPIC_API_KEY — it does not use Claude Code's")
    print("   own subscription quota.")


def _antigravity() -> None:
    _hr()
    print("Google Antigravity — MCP server (first-class support)\n")
    print("Google Antigravity supports MCP natively, so the config block is")
    print("identical to Claude Code — only the config file path differs.\n")
    print("1. Install:\n")
    print("   pip install 'query-oracle[mcp]'\n")
    print("2. Add this block to Antigravity's MCP config file")
    print("   (check your Antigravity docs for the exact path):\n")
    print(_MCP_JSON)
    print()
    print("3. Set ANTHROPIC_API_KEY in the environment Antigravity runs in.\n")
    print("⚠  Billing note: each route/classify call is a SEPARATE API call")
    print("   billed to your ANTHROPIC_API_KEY — it does not use Antigravity's")
    print("   own subscription quota.")


def _cursor() -> None:
    _hr()
    print("Cursor — VS Code extension (standalone, not woven into Cursor chat)\n")
    print("This repo ships a VS Code extension that opens a query input panel")
    print("(Cmd/Ctrl+Shift+L) and shows routing results in the output panel.")
    print("It starts its own REST server using your API key.\n")
    print("What it IS:  A standalone tool you invoke manually inside VS Code/Cursor.")
    print("What it ISN'T: It does not intercept or enhance Cursor's native AI chat.")
    print("               Cursor Agent, Tab, and Ask are unchanged.\n")
    print("Steps:\n")
    print("   cd vscode-extension")
    print("   npm install")
    print("   npm run package          # builds query-oracle-1.0.0.vsix")
    print("   code --install-extension query-oracle-1.0.0.vsix\n")
    print("Then set ANTHROPIC_API_KEY in your shell or a .env file in the workspace.\n")
    print("⚠  Billing note: uses your own ANTHROPIC_API_KEY, separate from any")
    print("   Cursor subscription.")


def _codex() -> None:
    _hr()
    print("Codex CLI — no native integration yet\n")
    print("query-oracle does not have a Codex CLI plugin today.")
    print("There is no hook point in the current Codex CLI for external routers.\n")
    print("Workaround — call /classify manually in scripts:\n")
    print("   # Get the routing tier before committing to a model call")
    print("   curl -s -X POST https://your-instance/classify \\")
    print('     -H "Authorization: Bearer $QUERY_ORACLE_API_KEY" \\')
    print('     -H "Content-Type: application/json" \\')
    print("     -d '{\"query\": \"your task here\"}' | jq .tier\n")
    print("If you want native Codex integration, open an issue:")
    print("   https://github.com/hemanpadvas2002/query-oracle/issues\n")
    print("Deploy your own REST instance first:")
    print("   pip install 'query-oracle[server]'")
    print("   export ANTHROPIC_API_KEY=sk-ant-...")
    print("   uvicorn server.rest_api:app --port 8000")


def _library_only() -> None:
    _hr()
    print("Library only — Python API\n")
    print("1. Install:\n")
    print("   pip install query-oracle\n")
    print("2. Create a .env file in your project:\n")
    for line in _ENV_SNIPPET.splitlines():
        print("   " + line)
    print()
    print("3. Use in code:\n")
    print("   from llm_router import QueryRouter")
    print("   r = QueryRouter().route('Your question here')")
    print("   print(r.content, r.tier.value, r.model_used)")


def main() -> None:
    _header()
    choice = _prompt_tool()
    handlers = {
        "1": _claude_code,
        "2": _antigravity,
        "3": _cursor,
        "4": _codex,
        "5": _library_only,
    }
    handlers[choice]()
    _hr()
    print("Done. Questions? https://github.com/hemanpadvas2002/query-oracle/issues\n")


if __name__ == "__main__":
    main()
