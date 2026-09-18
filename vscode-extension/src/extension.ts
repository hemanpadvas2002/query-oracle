/**
 * LLM Query Router — VS Code / Cursor Extension
 *
 * Auto-starts the bundled REST server on first use (no manual uvicorn needed).
 * Works in Cursor, VS Code, and any VS Code-based IDE.
 *
 * Quick start:
 *   1. Install the extension (.vsix or from Marketplace)
 *   2. Press Cmd/Ctrl+Shift+L — the server starts automatically
 *   3. Type your query — the router picks the right model
 */

import * as vscode from "vscode";
import { ensureServerRunning, stopServer } from "./server-manager";

interface RouteResponse {
  content:                string;
  tier:                   string;
  effort:                 string;
  provider:               string;
  model_used:             string;
  extended_thinking_used: boolean;
  input_tokens:           number;
  output_tokens:          number;
  latency_ms:             number;
  cost_usd:               number;
  classification: {
    tier:           string;
    effort:         string;
    facts_ratio:    number;
    judgment_ratio: number;
    confidence:     number;
    reasoning:      string;
  };
}

interface ClassifyResponse {
  tier:           string;
  effort:         string;
  facts_ratio:    number;
  judgment_ratio: number;
  confidence:     number;
  reasoning:      string;
}

let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext) {
  outputChannel = vscode.window.createOutputChannel("LLM Query Router");

  const askCmd = vscode.commands.registerCommand("llmRouter.ask", async () => {
    const query = await vscode.window.showInputBox({
      prompt: "Ask anything — the router picks the right model automatically",
      placeHolder: "e.g. How many calories in a banana? / Design an AI OS architecture...",
    });
    if (!query) return;
    if (!(await ensureReady(context))) return;
    await routeAndShow(query);
  });

  const askSelectionCmd = vscode.commands.registerCommand(
    "llmRouter.askSelection",
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) { vscode.window.showWarningMessage("No active editor."); return; }
      const selected = editor.document.getText(editor.selection).trim();
      if (!selected) { vscode.window.showWarningMessage("Select some text first."); return; }
      if (!(await ensureReady(context))) return;
      await routeAndShow(selected);
    }
  );

  const classifyCmd = vscode.commands.registerCommand(
    "llmRouter.classify",
    async () => {
      const query = await vscode.window.showInputBox({
        prompt: "Query to classify (no LLM call — just the routing decision)",
      });
      if (!query) return;
      if (!(await ensureReady(context))) return;
      await classifyAndShow(query);
    }
  );

  context.subscriptions.push(askCmd, askSelectionCmd, classifyCmd);
}

export function deactivate() {
  stopServer();
}

// ── helpers ───────────────────────────────────────────────────────────────────

async function ensureReady(context: vscode.ExtensionContext): Promise<boolean> {
  return ensureServerRunning(context.extensionPath, outputChannel);
}

function getConfig() {
  const cfg = vscode.workspace.getConfiguration("llmRouter");
  return {
    apiUrl:          cfg.get<string>("apiUrl",          "http://localhost:8000"),
    defaultProvider: cfg.get<string>("defaultProvider", "anthropic"),
    showMeta:        cfg.get<boolean>("showRoutingMetadata", true),
  };
}

async function routeAndShow(query: string): Promise<void> {
  const { apiUrl, defaultProvider, showMeta } = getConfig();

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "LLM Router: routing…", cancellable: false },
    async () => {
      try {
        const res = await fetch(`${apiUrl}/route`, {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ query, provider: defaultProvider }),
        });

        if (!res.ok) {
          vscode.window.showErrorMessage(`Router error: ${await res.text()}`);
          return;
        }

        const data: RouteResponse = await res.json();
        outputChannel.show(true);
        outputChannel.appendLine("─".repeat(70));
        outputChannel.appendLine(`Query: ${query}`);

        if (showMeta) {
          outputChannel.appendLine(
            `Tier: ${data.tier.toUpperCase()} | Model: ${data.model_used} | ` +
            `${data.latency_ms.toFixed(0)}ms | ` +
            `$${data.cost_usd.toFixed(5)} | ` +
            `${data.input_tokens}in / ${data.output_tokens}out tokens`
          );
          outputChannel.appendLine(
            `Routing: ${data.classification.reasoning} ` +
            `(confidence ${(data.classification.confidence * 100).toFixed(0)}%)`
          );
          outputChannel.appendLine("─".repeat(70));
        }

        outputChannel.appendLine(data.content);
        outputChannel.appendLine("");
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        vscode.window.showErrorMessage(
          `Could not reach router API at ${apiUrl}. Error: ${msg}`
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
