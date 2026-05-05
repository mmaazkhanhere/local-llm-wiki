import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("desktopApi", {
  checkBackendHealth: () => ipcRenderer.invoke("backend-health"),
  pickVaultFolder: () => ipcRenderer.invoke("vault-pick-folder"),
  openVaultPicker: () => ipcRenderer.invoke("vault-pick-folder"),
  selectVault: (path) => ipcRenderer.invoke("vault-select", path),
  bootstrapVault: (path) => ipcRenderer.invoke("vault-bootstrap", path),
  configureVault: (path) => ipcRenderer.invoke("vault-configure", path),
  vaultStatus: (path) => ipcRenderer.invoke("vault-status", path),
  testGroqKey: (vaultPath, apiKey) => ipcRenderer.invoke("provider-groq-test", vaultPath, apiKey),
  groqStatus: (vaultPath) => ipcRenderer.invoke("provider-groq-status", vaultPath),
  runRawIngest: (vaultPath) => ipcRenderer.invoke("raw-ingest-run", vaultPath),
  rawInbox: (vaultPath) => ipcRenderer.invoke("raw-inbox", vaultPath),
  startRawWatch: (vaultPath) => ipcRenderer.invoke("raw-watch-start", vaultPath),
  stopRawWatch: () => ipcRenderer.invoke("raw-watch-stop"),
  rawWatchStatus: () => ipcRenderer.invoke("raw-watch-status"),
  onBackendExited: (listener) => {
    ipcRenderer.on("backend-exited", (_, payload) => listener(payload));
  }
});
