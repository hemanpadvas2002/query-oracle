"""
Thin shim — delegates to the installed package MCP module.

Kept here for backwards-compatibility with existing claude_desktop_config.json
entries that point to this file path directly.

Preferred: use the installed console script instead.
  claude mcp add query-oracle -- query-oracle-mcp
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm_router.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
