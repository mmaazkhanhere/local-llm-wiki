from __future__ import annotations

from pathlib import Path

from llm_wiki.core.config import AppConfig
from llm_wiki.core.database import Database, initialize_schema, upsert_vault
from llm_wiki.ui.dashboard import build_dashboard_data, render_dashboard_text


def run_desktop_app(vault_root: Path, config: AppConfig) -> int:
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTextEdit, QVBoxLayout, QWidget
    except ImportError as exc:
        raise RuntimeError("PySide6 is not installed. Install it to use --ui.") from exc

    db = Database(vault_root / ".llm-wiki" / "app.db")
    with db.connect() as connection:
        initialize_schema(connection)
        upsert_vault(connection, vault_root)
        data = build_dashboard_data(connection=connection, config=config, vault_root=vault_root)
        dashboard_text = render_dashboard_text(data)

    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle("Local LLM Wiki")
    central = QWidget()
    layout = QVBoxLayout()
    layout.addWidget(QLabel("MVP Desktop Shell"))
    text = QTextEdit()
    text.setReadOnly(True)
    text.setPlainText(dashboard_text)
    layout.addWidget(text)
    central.setLayout(layout)
    window.setCentralWidget(central)
    window.resize(900, 640)
    window.show()
    return app.exec()
