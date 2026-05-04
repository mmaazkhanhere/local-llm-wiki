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
  onBackendExited: (listener) => {
    ipcRenderer.on("backend-exited", (_, payload) => listener(payload));
  }
});
