import { useEffect, useState } from "react";

const LAST_VAULT_PATH_KEY = "local-llm-wiki:last-vault-path";

const NAV_ITEMS = [
  "Dashboard",
  "Raw Inbox",
  "Proposed Updates",
  "Wiki Browser",
  "Ask",
  "Lint",
  "Settings"
];

export function App() {
  const [activeView, setActiveView] = useState("Dashboard");
  const [health, setHealth] = useState({ online: false, message: "Checking backend..." });
  const [vaultPath, setVaultPath] = useState("");
  const [status, setStatus] = useState({
    hasObsidian: false,
    gitDetected: false,
    obsidianCliAvailable: false
  });
  const [vaultMessage, setVaultMessage] = useState("No vault connected yet.");
  const [groqKey, setGroqKey] = useState("");
  const [providerState, setProviderState] = useState("Provider key has not been tested yet.");
  const [groqStatus, setGroqStatus] = useState({
    configured: false,
    connected: false,
    message: "Not configured.",
    model: "openai/gpt-oss-120b"
  });
  const [rawInboxFiles, setRawInboxFiles] = useState([]);
  const [rawInboxSummary, setRawInboxSummary] = useState(null);
  const [rawMessage, setRawMessage] = useState("No scan has run yet.");
  const [watchStatus, setWatchStatus] = useState({ running: false });

  function saveLastVaultPath(pathValue) {
    try {
      localStorage.setItem(LAST_VAULT_PATH_KEY, pathValue);
    } catch {
      // Ignore local storage write failures.
    }
  }

  function loadLastVaultPath() {
    try {
      return localStorage.getItem(LAST_VAULT_PATH_KEY);
    } catch {
      return null;
    }
  }

  function clearLastVaultPath() {
    try {
      localStorage.removeItem(LAST_VAULT_PATH_KEY);
    } catch {
      // Ignore local storage delete failures.
    }
  }

  async function restoreVault(pathValue) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !pathValue) return;
    const selected = await desktopApi.selectVault(pathValue);
    if (!selected.ok || !selected.payload) {
      clearLastVaultPath();
      setVaultPath("");
      setVaultMessage("Previously selected vault is no longer available. Please select again.");
      return;
    }
    setVaultPath(selected.payload.vault_path);
    await refreshVaultStatus(selected.payload.vault_path);
    await refreshGroqStatus(selected.payload.vault_path);
    await refreshRawInbox(selected.payload.vault_path);
    await ensureRawWatcherRunning(selected.payload.vault_path);
    const warning = selected.payload.warning ? ` Warning: ${selected.payload.warning}` : "";
    setVaultMessage(`Restored previous vault.${warning}`);
  }

  useEffect(() => {
    let mounted = true;
    const desktopApi = window.desktopApi;

    if (!desktopApi) {
      setHealth({
        online: false,
        message: "Desktop bridge not found. Open this UI through Electron, not a browser tab."
      });
      return () => {
        mounted = false;
      };
    }

    async function loadHealth() {
      const result = await desktopApi.checkBackendHealth();
      if (!mounted) return;
      if (result.online) {
        setHealth({ online: true, message: `Online (${result.payload.version})` });
      } else {
        setHealth({ online: false, message: `Offline (${result.message ?? "unreachable"})` });
      }
    }

    loadHealth();
    const lastVaultPath = loadLastVaultPath();
    if (lastVaultPath) {
      restoreVault(lastVaultPath);
    }
    const timer = setInterval(loadHealth, 60000);
    desktopApi.onBackendExited(() => {
      if (mounted) {
        setHealth({ online: false, message: "Offline (backend process exited)" });
      }
    });

    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  async function refreshVaultStatus(pathValue) {
    const desktopApi = window.desktopApi;
    if (!desktopApi) return;
    const statusResult = await desktopApi.vaultStatus(pathValue);
    if (statusResult.ok && statusResult.payload) {
      setStatus({
        hasObsidian: statusResult.payload.has_obsidian,
        gitDetected: statusResult.payload.git_detected,
        obsidianCliAvailable: statusResult.payload.obsidian_cli_available
      });
    }
  }

  async function refreshGroqStatus(pathValue) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !pathValue) return;
    const statusResult = await desktopApi.groqStatus(pathValue);
    if (!statusResult.ok || !statusResult.payload) {
      setGroqStatus({
        configured: false,
        connected: false,
        message: statusResult.error ?? "Unable to read Groq status.",
        model: "openai/gpt-oss-120b"
      });
      return;
    }
    setGroqStatus({
      configured: statusResult.payload.configured,
      connected: statusResult.payload.connected,
      message: statusResult.payload.message,
      model: statusResult.payload.default_text_model
    });
    if (statusResult.payload.connected) {
      setProviderState(`Connected: ${statusResult.payload.message}`);
    } else {
      setProviderState("Provider key has not been tested yet.");
    }
  }

  async function initializeVault(pathValue) {
    const desktopApi = window.desktopApi;
    if (!desktopApi) {
      setVaultMessage("Desktop bridge not found. Open this in Electron.");
      return;
    }
    try {
      const selected = await desktopApi.selectVault(pathValue);
      if (!selected.ok || !selected.payload) {
        setVaultMessage(`Vault selection failed: ${selected.error ?? "Unknown error"}`);
        return;
      }

      setVaultPath(selected.payload.vault_path);
      const bootstrap = await desktopApi.bootstrapVault(selected.payload.vault_path);
      if (!bootstrap.ok) {
        setVaultMessage(`Vault bootstrap failed: ${bootstrap.error ?? "Unknown error"}`);
        return;
      }

      const configured = await desktopApi.configureVault(selected.payload.vault_path);
      if (!configured.ok || !configured.payload) {
        setVaultMessage(`Vault config failed: ${configured.error ?? "Unknown error"}`);
        return;
      }

      setStatus({
        hasObsidian: configured.payload.has_obsidian,
        gitDetected: configured.payload.git_detected,
        obsidianCliAvailable: configured.payload.obsidian_cli_available
      });
      await refreshGroqStatus(configured.payload.vault_path);
      await refreshRawInbox(configured.payload.vault_path);
      await ensureRawWatcherRunning(configured.payload.vault_path);
      saveLastVaultPath(configured.payload.vault_path);
      const warning = configured.payload.warning ? ` Warning: ${configured.payload.warning}` : "";
      setVaultMessage(`Vault connected and initialized.${warning}`);
    } catch (error) {
      setVaultMessage(`Backend request failed: ${String(error)}`);
    }
  }

  async function connectVault() {
    const desktopApi = window.desktopApi;
    if (!desktopApi) {
      setVaultMessage("Desktop bridge not found. Open this in Electron.");
      return;
    }
    try {
      const pickFolder = desktopApi.pickVaultFolder ?? desktopApi.openVaultPicker;
      if (!pickFolder) {
        setVaultMessage("Vault picker bridge missing. Restart Electron so preload updates are applied.");
        return;
      }
      const picked = await pickFolder();
      if (picked.error) {
        setVaultMessage(`Vault picker failed: ${picked.error}`);
        return;
      }
      if (picked.canceled || !picked.path) {
        setVaultMessage("Vault selection canceled.");
        return;
      }
      await initializeVault(picked.path);
    } catch (error) {
      setVaultMessage(`Vault selection failed: ${String(error)}`);
    }
  }

  async function testGroqConnection() {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath) {
      setProviderState("Select and initialize a vault first.");
      return;
    }
    if (!groqKey.trim()) {
      setProviderState("Enter a Groq API key first.");
      return;
    }
    const result = await desktopApi.testGroqKey(vaultPath, groqKey.trim());
    if (!result.ok || !result.payload) {
      setProviderState(`Connection test failed: ${result.error ?? "Unknown error"}`);
      return;
    }
    if (result.payload.connected) {
      setProviderState(`Connected: ${result.payload.message}`);
      await refreshGroqStatus(vaultPath);
    } else {
      setProviderState(`Not connected: ${result.payload.message}`);
    }
  }

  async function refreshRawInbox(pathValue) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !pathValue) return;
    const result = await desktopApi.rawInbox(pathValue);
    if (!result.ok || !result.payload) {
      setRawMessage(`Raw Inbox unavailable: ${result.error ?? "Unknown error"}`);
      return;
    }
    setRawInboxFiles(result.payload.files ?? []);
    setRawInboxSummary(result.payload.summary ?? null);
  }

  async function runRawIngest() {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath) {
      setRawMessage("Select and initialize a vault first.");
      return;
    }
    setRawMessage("Running scan/hash/extract...");
    const result = await desktopApi.runRawIngest(vaultPath);
    if (!result.ok || !result.payload) {
      setRawMessage(`Raw ingest failed: ${result.error ?? "Unknown error"}`);
      return;
    }
    setRawMessage(
      `Ingest completed. processed=${result.payload.processed_count}, failed=${result.payload.failed_count}, pending_image=${result.payload.pending_image_count}`
    );
    await refreshRawInbox(vaultPath);
  }

  async function refreshWatchStatus() {
    const desktopApi = window.desktopApi;
    if (!desktopApi) return;
    const result = await desktopApi.rawWatchStatus();
    if (!result.ok || !result.payload) {
      setWatchStatus({ running: false });
      return;
    }
    setWatchStatus(result.payload);
  }

  async function ensureRawWatcherRunning(pathValue) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !pathValue) return;
    const status = await desktopApi.rawWatchStatus();
    if (
      status.ok &&
      status.payload &&
      status.payload.running &&
      status.payload.vault_path === pathValue
    ) {
      setWatchStatus(status.payload);
      return;
    }
    const started = await desktopApi.startRawWatch(pathValue);
    if (!started.ok || !started.payload) {
      setWatchStatus({ running: false });
      setRawMessage(`Failed to start watcher: ${started.error ?? "Unknown error"}`);
      return;
    }
    setWatchStatus(started.payload);
  }

  async function toggleRawWatch() {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath) {
      setRawMessage("Select and initialize a vault first.");
      return;
    }
    if (watchStatus.running) {
      await desktopApi.stopRawWatch();
      setRawMessage("Raw watcher stopped.");
      await refreshWatchStatus();
      return;
    }
    const result = await desktopApi.startRawWatch(vaultPath);
    if (!result.ok) {
      setRawMessage(`Failed to start watcher: ${result.error ?? "Unknown error"}`);
      return;
    }
    setRawMessage("Raw watcher started.");
    await refreshWatchStatus();
  }

  useEffect(() => {
    if (!vaultPath || !watchStatus.running) {
      return undefined;
    }
    const timer = setInterval(() => {
      refreshRawInbox(vaultPath);
    }, 1500);
    return () => clearInterval(timer);
  }, [vaultPath, watchStatus.running]);

  const isDashboard = activeView === "Dashboard";
  const isSettings = activeView === "Settings";
  const isRawInbox = activeView === "Raw Inbox";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>Local LLM Wiki</h1>
        <nav>
          {NAV_ITEMS.map((item) => (
            <button
              key={item}
              className={item === activeView ? "nav-btn active" : "nav-btn"}
              onClick={() => setActiveView(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="status-row">
          <div>
            <strong>Backend:</strong>{" "}
            <span className={health.online ? "ok" : "error"}>{health.message}</span>
          </div>
          <div>
            <strong>View:</strong> {activeView}
          </div>
        </header>

        <section className="panel">
          <h2>{activeView}</h2>
          {isDashboard && (
            <div className="stack">
              <button type="button" className="action-btn" onClick={connectVault}>
                Select Obsidian Vault
              </button>
              <p><strong>Selected vault:</strong> {vaultPath || "None"}</p>
              <p>{vaultMessage}</p>
              <p><strong>.obsidian:</strong> {status.hasObsidian ? "Found" : "Not found (warning only)"}</p>
              <p><strong>Git:</strong> {status.gitDetected ? "Enabled" : "Not enabled"}</p>
              <p>
                <strong>Groq:</strong>{" "}
                <span className={groqStatus.connected ? "ok" : "error"}>
                  {groqStatus.connected ? "Connected" : "Not connected"}
                </span>{" "}
                ({groqStatus.message})
              </p>
              <p><strong>Groq model:</strong> {groqStatus.model}</p>
              <p>
                <strong>Obsidian CLI:</strong> {status.obsidianCliAvailable ? "Available" : "Unavailable"}.
                Core functionality works without it.
              </p>
            </div>
          )}
          {isSettings && (
            <div className="stack">
              <p><strong>Selected vault:</strong> {vaultPath || "None"}</p>
              <button type="button" className="action-btn" onClick={connectVault}>
                Change Vault
              </button>
              <label htmlFor="groq-key">Groq API Key</label>
              <input
                id="groq-key"
                type="password"
                value={groqKey}
                onChange={(event) => setGroqKey(event.target.value)}
                placeholder="gsk_..."
              />
              <div className="row">
                <button type="button" className="action-btn" onClick={testGroqConnection}>
                  Test Connection
                </button>
                <button type="button" className="nav-btn" onClick={() => refreshVaultStatus(vaultPath)}>
                  Refresh Status
                </button>
                <button type="button" className="nav-btn" onClick={() => refreshGroqStatus(vaultPath)}>
                  Refresh Groq
                </button>
              </div>
              <p>
                Saved Groq key:{" "}
                <strong>{groqStatus.configured ? "Configured" : "Not configured"}</strong>
              </p>
              <p>
                Default Groq model: <strong>{groqStatus.model}</strong>
              </p>
              <p>{providerState}</p>
            </div>
          )}
          {isRawInbox && (
            <div className="stack">
              <div className="row">
                <button type="button" className="action-btn" onClick={runRawIngest}>
                  Run Raw Ingest
                </button>
                <button type="button" className="nav-btn" onClick={() => refreshRawInbox(vaultPath)}>
                  Refresh Inbox
                </button>
                <button type="button" className="nav-btn" onClick={toggleRawWatch}>
                  {watchStatus.running ? "Stop Watcher" : "Start Watcher"}
                </button>
              </div>
              <p><strong>Watcher:</strong> {watchStatus.running ? "Running" : "Stopped"}</p>
              {rawInboxSummary && (
                <p>
                  <strong>Summary:</strong> files={rawInboxSummary.discovered_count}, queued={rawInboxSummary.queued_count}, processed={rawInboxSummary.processed_count}, failed={rawInboxSummary.failed_count}, pending_image={rawInboxSummary.pending_image_count}
                </p>
              )}
              <p>{rawMessage}</p>
              <div>
                {rawInboxFiles.length === 0 && <p>No discovered files yet.</p>}
                {rawInboxFiles.length > 0 && (
                  <table>
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rawInboxFiles.map((file) => (
                        <tr key={file.relative_path}>
                          <td>{file.relative_path}</td>
                          <td>{file.file_type}</td>
                          <td>{file.processing_status}</td>
                          <td>{file.error_message || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              <p>Images are shown as <code>pending_image</code>. Image processing is not enabled yet.</p>
            </div>
          )}
          {!isDashboard && !isSettings && !isRawInbox && (
            <p>
              This is the Phase 0 UI shell placeholder for <strong>{activeView}</strong>.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
