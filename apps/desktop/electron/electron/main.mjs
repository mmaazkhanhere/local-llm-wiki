import { app, BrowserWindow, dialog, ipcMain } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, spawnSync } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..", "..", "..", "..");
const backendDir = path.join(projectRoot, "apps", "desktop", "backend");
const backendPort = 8765;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const isDev = !app.isPackaged;

let mainWindow = null;
let backendProcess = null;
let backendPid = null;
let stoppingBackend = false;

function killProcessTreeOnWindows(pid) {
  if (!pid) {
    return;
  }
  spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
    windowsHide: true,
    stdio: "ignore",
    timeout: 3000
  });
}

function killListenersOnBackendPort() {
  if (process.platform !== "win32") {
    return;
  }
  spawnSync(
    "powershell",
    [
      "-NoProfile",
      "-ExecutionPolicy",
      "Bypass",
      "-Command",
      `$port = ${backendPort}; ` +
        "$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; " +
        "if ($conns) { $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique; " +
        "foreach ($id in $pids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }"
    ],
    {
      windowsHide: true,
      stdio: "ignore",
      timeout: 3000
    }
  );
}

function startBackend() {
  if (backendProcess) {
    return;
  }
  killListenersOnBackendPort();

  backendProcess = spawn(
    "uv",
    ["run", "uvicorn", "llm_wiki_backend.main:app", "--host", "127.0.0.1", "--port", String(backendPort)],
    {
      cwd: backendDir,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true
    }
  );
  backendPid = backendProcess.pid ?? null;

  backendProcess.stdout.on("data", (chunk) => {
    const message = chunk.toString().trim();
    if (message.length > 0) {
      console.log(`[backend] ${message}`);
    }
  });

  backendProcess.stderr.on("data", (chunk) => {
    const message = chunk.toString().trim();
    if (message.length > 0) {
      console.error(`[backend] ${message}`);
    }
  });

  backendProcess.on("exit", (code) => {
    console.log(`[backend] exited with code ${code}`);
    backendProcess = null;
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("backend-exited", { code });
    }
  });
}

function stopBackend() {
  if (stoppingBackend) {
    return;
  }
  const pid = backendProcess?.pid ?? backendPid;
  if (!pid) {
    return;
  }

  stoppingBackend = true;
  if (process.platform === "win32") {
    killProcessTreeOnWindows(pid);
    // Defensive cleanup for uv-run child process trees that survive parent exit.
    killListenersOnBackendPort();
  } else {
    backendProcess?.kill("SIGTERM");
  }

  backendProcess = null;
  backendPid = null;
  stoppingBackend = false;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 780,
    title: "Local LLM Wiki",
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  if (isDev) {
    try {
      await mainWindow.loadURL("http://127.0.0.1:5173");
    } catch (error) {
      console.error(`[electron] failed to load dev URL: ${error}`);
      mainWindow.loadURL("data:text/html,<h2>Frontend failed to load</h2><p>Restart dev server and retry.</p>");
    }
  } else {
    await mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
  }
}

ipcMain.handle("backend-health", async () => {
  try {
    const response = await fetch(`${backendUrl}/health`, { method: "GET" });
    if (!response.ok) {
      return { online: false, message: `HTTP ${response.status}` };
    }
    const payload = await response.json();
    return { online: true, payload };
  } catch (error) {
    return { online: false, message: String(error) };
  }
});

ipcMain.handle("vault-pick-folder", async () => {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return { canceled: true, path: null, error: "Main window is not available." };
  }
  try {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory"]
    });
    if (result.canceled || result.filePaths.length === 0) {
      return { canceled: true, path: null };
    }
    return { canceled: false, path: result.filePaths[0] };
  } catch (error) {
    return { canceled: true, path: null, error: String(error) };
  }
});

async function backendPost(route, body, query = "") {
  try {
    const response = await fetch(`${backendUrl}${route}${query}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const payload = await response.json();
    if (!response.ok) {
      return { ok: false, status: response.status, error: payload?.detail ?? "Request failed" };
    }
    return { ok: true, payload };
  } catch (error) {
    return { ok: false, status: 503, error: `Backend unavailable: ${String(error)}` };
  }
}

async function backendGet(route, query = "") {
  try {
    const response = await fetch(`${backendUrl}${route}${query}`, { method: "GET" });
    const payload = await response.json();
    if (!response.ok) {
      return { ok: false, status: response.status, error: payload?.detail ?? "Request failed" };
    }
    return { ok: true, payload };
  } catch (error) {
    return { ok: false, status: 503, error: `Backend unavailable: ${String(error)}` };
  }
}

ipcMain.handle("vault-select", async (_, pathValue) => backendPost("/vault/select", { path: pathValue }));

ipcMain.handle("vault-bootstrap", async (_, pathValue) => backendPost("/vault/bootstrap", { path: pathValue }));
ipcMain.handle("vault-reset", async (_, pathValue) => backendPost("/vault/reset", { path: pathValue }));

ipcMain.handle("vault-configure", async (_, pathValue) => backendPost("/vault/configure", { path: pathValue }));

ipcMain.handle("vault-status", async (_, pathValue) =>
  backendGet("/vault/status", `?vault_path=${encodeURIComponent(pathValue)}`)
);

ipcMain.handle("provider-groq-test", async (_, vaultPath, apiKey) =>
  backendPost("/provider/groq/test", { api_key: apiKey }, `?vault_path=${encodeURIComponent(vaultPath)}`)
);

ipcMain.handle("provider-groq-status", async (_, vaultPath) =>
  backendGet("/provider/groq/status", `?vault_path=${encodeURIComponent(vaultPath)}`)
);

ipcMain.handle("raw-ingest-run", async (_, vaultPath) =>
  backendPost("/ingest/raw/run", {}, `?vault_path=${encodeURIComponent(vaultPath)}`)
);

ipcMain.handle("raw-inbox", async (_, vaultPath) =>
  backendGet("/ingest/raw/inbox", `?vault_path=${encodeURIComponent(vaultPath)}`)
);

ipcMain.handle("raw-watch-start", async (_, vaultPath) =>
  backendPost("/ingest/raw/watch/start", {}, `?vault_path=${encodeURIComponent(vaultPath)}`)
);

ipcMain.handle("raw-watch-stop", async () => backendPost("/ingest/raw/watch/stop", {}));

ipcMain.handle("raw-watch-status", async () => backendGet("/ingest/raw/watch/status"));

app.whenReady().then(async () => {
  startBackend();
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("will-quit", () => {
  stopBackend();
});

process.on("SIGINT", () => {
  stopBackend();
  app.quit();
});

process.on("SIGTERM", () => {
  stopBackend();
  app.quit();
});

process.on("exit", () => {
  stopBackend();
});
