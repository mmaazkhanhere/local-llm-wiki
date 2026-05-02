import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("desktopApi", {
  checkBackendHealth: () => ipcRenderer.invoke("backend-health"),
  onBackendExited: (listener) => {
    ipcRenderer.on("backend-exited", (_, payload) => listener(payload));
  }
});
