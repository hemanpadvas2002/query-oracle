/**
 * Manages the lifecycle of the bundled REST API server.
 * Spawns `python -m uvicorn server.rest_api:app` from the repo root,
 * waits until it is reachable, and tears it down on deactivation.
 */

import * as vscode from "vscode";
import * as cp from "child_process";
import * as path from "path";
import * as fs from "fs";

let serverProcess: cp.ChildProcess | null = null;
let outputChannel: vscode.OutputChannel | null = null;

/** Resolve the repo root (parent of the extension's install directory). */
function repoRoot(extensionPath: string): string {
  // When installed from .vsix the layout is:
  //   <ext>/  ← extensionPath
  // When running from source (F5) the layout is:
  //   llm-query-router/vscode-extension/  ← extensionPath
  // We try the parent; if server/rest_api.py is there, that's the root.
  const parent = path.dirname(extensionPath);
  if (fs.existsSync(path.join(parent, "server", "rest_api.py"))) return parent;
  // Fallback: let the user configure it.
  return "";
}

function getConfig() {
  const cfg = vscode.workspace.getConfiguration("llmRouter");
  return {
    apiUrl:        cfg.get<string>("apiUrl",        "http://localhost:8000"),
    pythonPath:    cfg.get<string>("pythonPath",    "python"),
    autoStart:     cfg.get<boolean>("autoStart",    true),
    serverPort:    cfg.get<number>("serverPort",    8000),
  };
}

/** Return true if the server is already reachable. */
async function isReachable(url: string): Promise<boolean> {
  try {
    const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(1500) });
    return res.ok;
  } catch {
    return false;
  }
}

/** Poll until the server responds or timeout (ms) is reached. */
async function waitUntilReady(url: string, timeoutMs = 12_000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await isReachable(url)) return true;
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

export async function ensureServerRunning(
  extensionPath: string,
  channel: vscode.OutputChannel
): Promise<boolean> {
  outputChannel = channel;
  const { apiUrl, pythonPath, autoStart, serverPort } = getConfig();

  if (await isReachable(apiUrl)) return true;   // already up
  if (!autoStart) {
    vscode.window.showWarningMessage(
      `LLM Router: server not reachable at ${apiUrl}. ` +
      `Enable "llmRouter.autoStart" or start it manually.`
    );
    return false;
  }

  const root = repoRoot(extensionPath);
  if (!root) {
    vscode.window.showErrorMessage(
      "LLM Router: cannot locate repo root. Set llmRouter.serverRepoPath in settings."
    );
    return false;
  }

  channel.appendLine(`[server-manager] Starting REST server on port ${serverPort}…`);

  serverProcess = cp.spawn(
    pythonPath,
    ["-m", "uvicorn", "server.rest_api:app", "--port", String(serverPort), "--host", "127.0.0.1"],
    { cwd: root, env: { ...process.env } }
  );

  serverProcess.stdout?.on("data", (d) => channel.append(`[server] ${d}`));
  serverProcess.stderr?.on("data", (d) => channel.append(`[server] ${d}`));
  serverProcess.on("exit", (code) => {
    channel.appendLine(`[server-manager] Server exited (code ${code})`);
    serverProcess = null;
  });

  const ready = await waitUntilReady(apiUrl);
  if (ready) {
    channel.appendLine("[server-manager] Server ready.");
  } else {
    vscode.window.showErrorMessage(
      "LLM Router: server did not start in time. Check the output panel for errors."
    );
    channel.show(true);
  }
  return ready;
}

export function stopServer(): void {
  if (serverProcess) {
    serverProcess.kill();
    serverProcess = null;
    outputChannel?.appendLine("[server-manager] Server stopped.");
  }
}
