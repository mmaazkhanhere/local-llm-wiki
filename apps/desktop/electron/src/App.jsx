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
  const [wikiGeneration, setWikiGeneration] = useState(null);
  const [eventsConnected, setEventsConnected] = useState(false);
  const [reviewProposals, setReviewProposals] = useState([]);
  const [selectedProposalId, setSelectedProposalId] = useState("");
  const [selectedProposal, setSelectedProposal] = useState(null);
  const [reviewEditorContent, setReviewEditorContent] = useState("");
  const [reviewMessage, setReviewMessage] = useState("No pending proposals yet.");
  const [reviewBusy, setReviewBusy] = useState(false);

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
    await refreshReviews(selected.payload.vault_path);
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
    if (!desktopApi || !pathValue) return;
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
      await refreshReviews(configured.payload.vault_path);
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

  async function refreshReviews(pathValue, keepSelected = true) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !pathValue) return;
    const result = await desktopApi.reviewList(pathValue, "pending");
    if (!result.ok || !result.payload) {
      setReviewMessage(`Proposed updates unavailable: ${result.error ?? "Unknown error"}`);
      setReviewProposals([]);
      setSelectedProposal(null);
      setSelectedProposalId("");
      return;
    }
    const proposals = (result.payload.proposals ?? []).slice().sort((left, right) => {
      const leftKey = `${left.target_title ?? ""}`.toLowerCase();
      const rightKey = `${right.target_title ?? ""}`.toLowerCase();
      return leftKey.localeCompare(rightKey);
    });
    setReviewProposals(proposals);
    if (proposals.length === 0) {
      setSelectedProposal(null);
      setSelectedProposalId("");
      setReviewEditorContent("");
      setReviewMessage("No pending proposals yet.");
      return;
    }
    if (selectedProposalId && !proposals.some((item) => item.id === selectedProposalId)) {
      setSelectedProposalId("");
      setSelectedProposal(null);
      setReviewEditorContent("");
    }
    const preferredId =
      keepSelected && selectedProposalId && proposals.some((item) => item.id === selectedProposalId)
        ? selectedProposalId
        : proposals[0].id;
    await loadProposal(pathValue, preferredId);
    setReviewMessage(`Loaded ${proposals.length} pending proposal${proposals.length === 1 ? "" : "s"}.`);
  }

  async function loadProposal(pathValue, proposalId) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !pathValue || !proposalId) return;
    const result = await desktopApi.reviewGet(pathValue, proposalId);
    if (!result.ok || !result.payload) {
      setReviewMessage(`Failed to load proposal: ${result.error ?? "Unknown error"}`);
      return;
    }
    setSelectedProposalId(proposalId);
    setSelectedProposal(result.payload);
    setReviewEditorContent(result.payload.proposed_content ?? "");
  }

  function removeProposalFromList(proposalId) {
    setReviewProposals((current) => current.filter((item) => item.id !== proposalId));
    if (selectedProposalId === proposalId) {
      setSelectedProposalId("");
      setSelectedProposal(null);
      setReviewEditorContent("");
    }
  }

  function updateProposalInList(updatedProposal) {
    if (!updatedProposal?.id) return;
    setReviewProposals((current) => {
      const next = current.map((item) => (item.id === updatedProposal.id ? { ...item, ...updatedProposal } : item));
      next.sort((left, right) => {
        const leftKey = `${left.target_title ?? ""}`.toLowerCase();
        const rightKey = `${right.target_title ?? ""}`.toLowerCase();
        return leftKey.localeCompare(rightKey);
      });
      return next;
    });
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
      setWikiGeneration(null);
      return;
    }
    setWikiGeneration(result.payload.wiki_generation ?? null);
    const wikiSummary = result.payload.wiki_generation;
    const wikiSuffix = wikiSummary
      ? ` wiki_pages=${wikiSummary.generated_page_count}, flashcards=${wikiSummary.generated_flashcard_count}, proposals=${wikiSummary.proposed_update_count}, wiki_failures=${wikiSummary.failed_count}`
      : "";
    setRawMessage(
      `Ingest completed. processed=${result.payload.processed_count}, failed=${result.payload.failed_count}, pending_image=${result.payload.pending_image_count}${wikiSuffix}`
    );
    await refreshRawInbox(vaultPath);
    await refreshReviews(vaultPath, false);
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
    const statusResult = await desktopApi.rawWatchStatus();
    if (
      statusResult.ok &&
      statusResult.payload &&
      statusResult.payload.running &&
      statusResult.payload.vault_path === pathValue
    ) {
      setWatchStatus(statusResult.payload);
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

  async function saveEditedProposal() {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath || !selectedProposal) return;
    setReviewBusy(true);
    const result = await desktopApi.reviewEdit(vaultPath, selectedProposal.id, reviewEditorContent);
    setReviewBusy(false);
    if (!result.ok || !result.payload) {
      setReviewMessage(`Edit failed: ${result.error ?? "Unknown error"}`);
      return;
    }
    setSelectedProposal(result.payload);
    setReviewEditorContent(result.payload.proposed_content);
    updateProposalInList(result.payload);
    setReviewMessage("Edited proposal saved.");
    await refreshReviews(vaultPath);
  }

  async function approveProposal() {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath || !selectedProposal) return;
    setReviewBusy(true);
    const result = await desktopApi.reviewApprove(vaultPath, selectedProposal.id);
    setReviewBusy(false);
    if (!result.ok || !result.payload) {
      setReviewMessage(`Approve failed: ${result.error ?? "Unknown error"}`);
      return;
    }
    setSelectedProposal(result.payload);
    if (result.payload.status === "approved") {
      removeProposalFromList(result.payload.id);
      setReviewMessage(`Approved update for ${result.payload.target_title}.`);
    } else {
      updateProposalInList(result.payload);
      setReviewMessage(result.payload.last_error ?? `Approve did not apply (status=${result.payload.status}).`);
    }
    await refreshReviews(vaultPath, false);
  }

  async function rejectProposal() {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath || !selectedProposal) return;
    setReviewBusy(true);
    const result = await desktopApi.reviewReject(vaultPath, selectedProposal.id);
    setReviewBusy(false);
    if (!result.ok || !result.payload) {
      setReviewMessage(`Reject failed: ${result.error ?? "Unknown error"}`);
      return;
    }
    removeProposalFromList(result.payload.id);
    setReviewMessage(`Rejected update for ${result.payload.target_title}.`);
    await refreshReviews(vaultPath, false);
  }

  async function approveAllForSource(sourceRelativePath) {
    const desktopApi = window.desktopApi;
    if (!desktopApi || !vaultPath || !sourceRelativePath) return;
    setReviewBusy(true);
    const result = await desktopApi.reviewApproveAll(vaultPath, sourceRelativePath);
    setReviewBusy(false);
    if (!result.ok || !result.payload) {
      setReviewMessage(`Approve all failed: ${result.error ?? "Unknown error"}`);
      return;
    }
    setReviewMessage(
      `${result.payload.applied} applied, ${result.payload.conflicted} conflicted, ${result.payload.failed} failed for ${sourceRelativePath}.`
    );
    await refreshReviews(vaultPath, false);
  }

  useEffect(() => {
    if (!vaultPath || !watchStatus.running) {
      return undefined;
    }
    let cancelled = false;
    const socket = new WebSocket(`ws://127.0.0.1:8765/ws/events?vault_path=${encodeURIComponent(vaultPath)}`);

    let pollTimer = setInterval(() => {
      refreshRawInbox(vaultPath);
      refreshReviews(vaultPath);
    }, 3000);

    socket.onopen = () => {
      if (cancelled) return;
      setEventsConnected(true);
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };
    socket.onclose = () => {
      if (cancelled) return;
      setEventsConnected(false);
      if (!pollTimer) {
        pollTimer = setInterval(() => {
          refreshRawInbox(vaultPath);
          refreshReviews(vaultPath);
        }, 3000);
      }
    };
    socket.onerror = () => {
      if (cancelled) return;
      setEventsConnected(false);
      if (!pollTimer) {
        pollTimer = setInterval(() => {
          refreshRawInbox(vaultPath);
          refreshReviews(vaultPath);
        }, 3000);
      }
    };
    socket.onmessage = () => {
      if (cancelled) return;
      refreshRawInbox(vaultPath);
      refreshReviews(vaultPath);
    };

    return () => {
      cancelled = true;
      setEventsConnected(false);
      if (pollTimer) {
        clearInterval(pollTimer);
      }
      try {
        socket.close();
      } catch {
        // ignore
      }
    };
  }, [vaultPath, watchStatus.running, selectedProposalId]);

  const isDashboard = activeView === "Dashboard";
  const isSettings = activeView === "Settings";
  const isRawInbox = activeView === "Raw Inbox";
  const isProposedUpdates = activeView === "Proposed Updates";

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
            <strong>Watcher:</strong> {watchStatus.running ? "Running" : "Stopped"} /{" "}
            {eventsConnected ? "Live events" : "Polling"}
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
              <p><strong>Pending proposals:</strong> {reviewProposals.length}</p>
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
              {wikiGeneration && (
                <div className="stack">
                  <p>
                    <strong>Wiki generation:</strong> sources={wikiGeneration.attempted_source_count},
                    pages={wikiGeneration.generated_page_count}, flashcards={wikiGeneration.generated_flashcard_count},
                    proposals={wikiGeneration.proposed_update_count}, failed={wikiGeneration.failed_count}
                  </p>
                  {wikiGeneration.skipped_reason && <p>{wikiGeneration.skipped_reason}</p>}
                  {wikiGeneration.source_results?.length > 0 && (
                    <table>
                      <thead>
                        <tr>
                          <th>Source</th>
                          <th>Status</th>
                          <th>Candidates</th>
                          <th>Output</th>
                        </tr>
                      </thead>
                      <tbody>
                        {wikiGeneration.source_results.map((result) => (
                          <tr key={result.source_path}>
                            <td>{result.source_path}</td>
                            <td>{result.status}</td>
                            <td>
                              {(result.candidates ?? []).map((candidate) => candidate.title).join(", ") || "-"}
                            </td>
                            <td>
                              {[...(result.generated_page_paths ?? []), result.flashcard_path]
                                .filter(Boolean)
                                .join(", ") ||
                                (result.proposed_updates ?? []).map((proposal) => proposal.target_title).join(", ") ||
                                result.error_message ||
                                "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
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
          {isProposedUpdates && (
            <div className="review-layout">
              <section className="review-list">
                <div className="row">
                  <button type="button" className="action-btn" onClick={() => refreshReviews(vaultPath, false)}>
                    Refresh Proposals
                  </button>
                </div>
                <p>{reviewMessage}</p>
                {reviewProposals.length === 0 && <p>No pending proposals.</p>}
                {reviewProposals.length > 0 && (
                  <div className="stack">
                    {reviewProposals.map((proposal) => (
                      <button
                        key={proposal.id}
                        type="button"
                        className={proposal.id === selectedProposalId ? "proposal-btn active" : "proposal-btn"}
                        onClick={() => loadProposal(vaultPath, proposal.id)}
                      >
                        <span>
                          <strong>{proposal.target_title}</strong>
                          <div className="muted">{proposal.target_relative_path}</div>
                          <div className="muted">Source: {proposal.source_relative_path}</div>
                          {proposal.status === "conflicted" && (
                            <div className="muted">Conflict: target changed since proposal creation</div>
                          )}
                          {proposal.last_error && <div className="muted">Last error: {proposal.last_error}</div>}
                        </span>
                        <span className="muted">{proposal.confidence || proposal.status || "pending"}</span>
                      </button>
                    ))}
                  </div>
                )}
              </section>

              <section className="review-detail">
                {!selectedProposal && <p>Select a proposal to inspect the diff and proposed content.</p>}
                {selectedProposal && (
                  <div className="stack">
                    <div className="review-summary">
                      <div>
                        <h3>{selectedProposal.target_title}</h3>
                        <p><strong>Target:</strong> {selectedProposal.target_relative_path}</p>
                        <p><strong>Source:</strong> {selectedProposal.source_relative_path}</p>
                        <p><strong>Reason:</strong> {selectedProposal.reason}</p>
                        <p><strong>Status:</strong> {selectedProposal.status}</p>
                        {selectedProposal.last_error && <p><strong>Last error:</strong> {selectedProposal.last_error}</p>}
                      </div>
                      <div className="stack">
                        <button type="button" className="action-btn" disabled={reviewBusy} onClick={saveEditedProposal}>
                          Save Edit
                        </button>
                        <button type="button" className="action-btn success-btn" disabled={reviewBusy} onClick={approveProposal}>
                          Approve
                        </button>
                        <button type="button" className="danger-btn" disabled={reviewBusy} onClick={rejectProposal}>
                          Reject
                        </button>
                        <button
                          type="button"
                          className="nav-btn"
                          disabled={reviewBusy}
                          onClick={() => approveAllForSource(selectedProposal.source_relative_path)}
                        >
                          Approve All From Source
                        </button>
                      </div>
                    </div>
                    {selectedProposal.source_citations?.length > 0 && (
                      <div className="stack">
                        <strong>Citations</strong>
                        {selectedProposal.source_citations.map((citation, index) => (
                          <code key={`${citation.locator}-${index}`}>{citation.locator}</code>
                        ))}
                      </div>
                    )}
                    <div className="diff-panel">
                      <h4>Visual Diff</h4>
                      <div className="diff-viewer">
                        {(selectedProposal.diff ?? []).map((line, index) => (
                          <div key={`${line.kind}-${index}`} className={`diff-line ${line.kind}`}>
                            {line.text || " "}
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="editor-grid">
                      <div>
                        <h4>Current Content</h4>
                        <pre className="content-box">{selectedProposal.old_content}</pre>
                      </div>
                      <div>
                        <h4>Proposed Content</h4>
                        <textarea
                          className="editor-box"
                          value={reviewEditorContent}
                          onChange={(event) => setReviewEditorContent(event.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}
          {!isDashboard && !isSettings && !isRawInbox && !isProposedUpdates && (
            <p>
              This is the Phase 0 UI shell placeholder for <strong>{activeView}</strong>.
            </p>
          )}
        </section>
      </main>
    </div>
  );
}
