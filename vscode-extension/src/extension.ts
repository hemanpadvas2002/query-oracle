/**
 * LLM Query Router — VS Code / Cursor Extension
 *
 * Sends queries to the local REST API server and shows routed responses
 * in an output panel. Works in Cursor, VS Code, and any VS Code-based IDE.
 *
 * Setup:
 *   1. Start the REST server: uvicorn server.rest_api:app --port 8000
 *   2. Install extension: Press F5 in VS Code to run in debug mode,
 *      or `vsce package` to build a .vsix for installation.
 *   3. Press Cmd/Ctrl+Shift+L to ask a question.
 */

import * as vscode from "vscode";

interface RouteResponse {
  content: string;
  tier: string;
  effort: string;
  provider: string;
  model_used: string;
  extended_thinking_used: boolean;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  classification: {
    tier: string;
    effort: string;
    facts_ratio: number;
    judgment_ratio: number;
    confidence: number;
    reasoning: string;
  };
}

interface ClassifyResponse {
  tier: string;
  effort: string;
  facts_ratio: number;
  judgment_ratio: number;
  confidence: number;
  reasoning: string;
}

let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
  outputChannel = vscode.window.createOutputChannel("LLM Query Router");

  // ── Command: Ask (auto-route) ─────────────────────────────────────────
  const askCmd = vscode.commands.registerCommand("llmRouter.ask", async () => {
    const query = await vscode.window.showInputBox({
      prompt: "Ask anything — the router picks the right model automatically",
      placeHolder: "e.g. How many calories in a banana? / Design an AI OS architecture...",
    });
    if (!query) return;
    await routeAndShow(query);
  });

  // ── Command: Ask with selected text ──────────────────────────────────
  const askSelectionCmd = vscode.commands.registerCommand(
    "llmRouter.askSelection",
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("No active editor.");
        return;
      }
      const selected = editor.document.getText(editor.selection).trim();
      if (!selected) {
        vscode.window.showWarningMessage("Select some text first.");
        return;
      }
      await routeAndShow(selected);
    }
  );

  // ── Command: Classify only ────────────────────────────────────────────
  const classifyCmd = vscode.commands.registerCommand(
    "llmRouter.classify",
    async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Query to classify (no LLM call, just routing decision)",
      });
      if (!query) return;
      await classifyAndShow(query);
    }
  );

  context.subscriptions.push(askCmd, askSelectionCmd, classifyCmd);
}

export function deactivate() {}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getConfig() {
  const cfg = vscode.workspace.getConfiguration("llmRouter");
  return {
    apiUrl:           cfg.get<string>("apiUrl", "http://localhost:8000"),
    defaultProvider:  cfg.get<string>("defaultProvider", "anthropic"),
    showMeta:         cfg.get<boolean>("showRoutingMetadata", true),
  };
}

async function routeAndShow(query: string): Promise<void> {
  const { apiUrl, defaultProvider, showMeta } = getConfig();

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "LLM Router: routing query…",
      cancellable: false,
    },
    async () => {
      try {
        const res = await fetch(`${apiUrl}/route`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ query, provider: defaultProvider }),
        });

        if (!res.ok) {
          const err = await res.text();
          vscode.window.showErrorMessage(`Router error: ${err}`);
          return;
        }

        const data: RouteResponse = await res.json();
        outputChannel.show(true);
        outputChannel.appendLine("─".repeat(70));
        outputChannel.appendLine(`Query: ${query}`);

        if (showMeta) {
          outputChannel.appendLine(
            `Tier: ${data.tier.toUpperCase()} | Model: ${data.model_used} | ` +
            `Provider: ${data.provider} | Extended thinking: ${data.extended_thinking_used} | ` +
            `${data.latency_ms.toFixed(0)}ms | ` +
            `${data.input_tokens}in/${data.output_tokens}out tokens`
          );
          outputChannel.appendLine(
            `Classifier: ${data.classification.reasoning} (confidence ${(data.classification.confidence * 100).toFixed(0)}%)`
          );
          outputChannel.appendLine("─".repeat(70));
        }

        outputChannel.appendLine(data.content);
        outputChannel.appendLine("");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(
          `Could not reach router API at ${apiUrl}. Is the server running? Error: ${msg}`
        );
      }
    }
  );
}

async function classifyAndShow(query: string): Promise<void> {
  const { apiUrl } = getConfig();
  try {
    const res  = await fetch(`${apiUrl}/classify`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ query }),
    });
    const data: ClassifyResponse = await res.json();
    const msg = (
      `Tier: ${data.tier} | Effort: ${data.effort} | ` +
      `Confidence: ${(data.confidence * 100).toFixed(0)}% — ${data.reasoning}`
    );
    vscode.window.showInformationMessage(msg);
  } catch {
    vscode.window.showErrorMessage(`Could not reach router API at ${apiUrl}.`);
  }
}
