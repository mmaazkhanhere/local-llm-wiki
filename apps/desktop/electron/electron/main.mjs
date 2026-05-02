import { app, BrowserWindow, ipcMain } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..", "..", "..");
const backendDir = path.join(projectRoot, "apps", "desktop", "backend");
const backendPort = 8765;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const isDev = !app.isPackaged;

let mainWindow = null;
let backendProcess = null;

function startBackend() {
  if (backendProcess) {
    return;
  }

  backendProcess = spawn(
    "uv",
    ["run", "uvicorn", "llm_wiki_backend.main:app", "--host", "127.0.0.1", "--port", String(backendPort)],
    {
      cwd: backendDir,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true
    }
  );

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
  if (!backendProcess) {
    return;
  }
  backendProcess.kill();
  backendProcess = null;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 780,
    title: "Local LLM Wiki",
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false
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
