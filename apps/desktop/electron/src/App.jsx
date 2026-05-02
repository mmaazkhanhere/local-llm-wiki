import { useEffect, useState } from "react";

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
    const timer = setInterval(loadHealth, 5000);
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
          <p>
            This is the Phase 0 UI shell placeholder for <strong>{activeView}</strong>.
          </p>
        </section>
      </main>
    </div>
  );
}
