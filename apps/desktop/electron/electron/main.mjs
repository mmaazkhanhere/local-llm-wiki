import { app, BrowserWindow, dialog, ipcMain } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import net from "node:net";
import { execFile } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..", "..", "..", "..");
const backendDir = path.join(projectRoot, "apps", "desktop", "backend");
const backendPort = 8765;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const isDev = !app.isPackaged;

let mainWindow = null;
let backendProcess = null;
let stoppingBackend = false;

function backendPidFilePath() {
  return path.join(app.getPath("userData"), "backend.pid");
}

async function writeBackendPid(pid) {
  if (!pid) return;
  try {
    await fs.mkdir(app.getPath("userData"), { recursive: true });
    await fs.writeFile(backendPidFilePath(), String(pid), "utf-8");
  } catch {
    // Best-effort only.
  }
}

async function readBackendPid() {
  try {
    const contents = await fs.readFile(backendPidFilePath(), "utf-8");
    const pid = Number.parseInt(contents.trim(), 10);
    return Number.isFinite(pid) ? pid : null;
  } catch {
    return null;
  }
}

async function clearBackendPid() {
  try {
    await fs.unlink(backendPidFilePath());
  } catch {
    // Ignore.
  }
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    const timer = setTimeout(() => {
      socket.destroy();
      resolve(false);
    }, 250);
    socket.once("error", () => {
      clearTimeout(timer);
      resolve(false);
    });
    socket.connect(port, "127.0.0.1", () => {
      clearTimeout(timer);
      socket.end();
      resolve(true);
    });
  });
}

function execFilePromise(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile(command, args, options, (error, stdout, stderr) => {
      if (error) {
        reject(Object.assign(error, { stdout, stderr }));
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

async function pidListeningOnPort(port) {
  if (process.platform !== "win32") {
    return null;
  }
  try {
    const { stdout } = await execFilePromise("netstat", ["-ano", "-p", "tcp"], { windowsHide: true });
    const lines = String(stdout || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    for (const line of lines) {
      if (!line.startsWith("TCP")) continue;
      const parts = line.split(/\s+/);
      // netstat columns: Proto LocalAddress ForeignAddress State PID
      if (parts.length < 5) continue;
      const local = parts[1];
      const state = parts[3];
      const pid = parts[4];
      if (state !== "LISTENING") continue;
      if (!local.endsWith(`:${port}`)) continue;
      const parsed = Number.parseInt(pid, 10);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  } catch {
    return null;
  }
  return null;
}

async function killPid(pid) {
  if (!pid) return false;
  try {
    if (process.platform === "win32") {
      await execFilePromise("taskkill", ["/PID", String(pid), "/T", "/F"], { windowsHide: true });
      return true;
    }
    process.kill(pid, "SIGTERM");
    return true;
  } catch {
    return false;
  }
}

async function stopBackend() {
  if (!backendProcess || stoppingBackend) {
    await clearBackendPid();
    return;
  }
  stoppingBackend = true;
  const pid = backendProcess.pid;

  const waitForExit = new Promise((resolve) => {
    backendProcess.once("exit", () => resolve());
    backendProcess.once("close", () => resolve());
  });

  if (process.platform === "win32" && pid) {
    const killer = spawn("taskkill", ["/PID", String(pid), "/T", "/F"], {
      windowsHide: true,
      stdio: "ignore"
    });
    killer.on("exit", async () => {
      await waitForExit;
      backendProcess = null;
      stoppingBackend = false;
      await clearBackendPid();
    });
    killer.on("error", async () => {
      backendProcess?.kill();
      await waitForExit;
      backendProcess = null;
      stoppingBackend = false;
      await clearBackendPid();
    });
    return;
  }

  backendProcess.kill();
  await waitForExit;
  backendProcess = null;
  stoppingBackend = false;
  await clearBackendPid();
}

async function startBackend() {
  if (backendProcess) {
    return;
  }

  const alreadyRunning = await isPortOpen(backendPort);
  if (alreadyRunning) {
    const previousPid = await readBackendPid();
    if (previousPid) {
      await killPid(previousPid);
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }

  if (await isPortOpen(backendPort)) {
    const pid = await pidListeningOnPort(backendPort);
    if (pid) {
      const killed = await killPid(pid);
      if (killed) {
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
    }
  }

  if (await isPortOpen(backendPort)) {
    const pid = await pidListeningOnPort(backendPort);
    const pidText = pid ? ` (pid=${pid})` : "";
    console.error(`[backend] port ${backendPort} is already in use${pidText}; not starting a new backend`);
    return;
  }

  backendProcess = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "llm_wiki_backend.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(backendPort),
      "--no-access-log"
    ],
    {
      cwd: backendDir,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true
    }
  );

  await writeBackendPid(backendProcess.pid);

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
    clearBackendPid();
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("backend-exited", { code });
    }
  });
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

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
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
  await startBackend();
  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  (async () => {
    await stopBackend();
    if (process.platform !== "darwin") {
      app.quit();
    }
  })();
});

app.on("before-quit", async (event) => {
  if (stoppingBackend) {
    return;
  }
  if (backendProcess) {
    event.preventDefault();
    await stopBackend();
    app.quit();
  }
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
