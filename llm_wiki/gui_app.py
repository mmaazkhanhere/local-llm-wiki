from __future__ import annotations

import sqlite3
from pathlib import Path

from llm_wiki.app import (
    build_provider,
    process_scanned_file,
    provider_ping,
)
from llm_wiki.core.config import AppConfig, load_config, save_config
from llm_wiki.core.database import Database, initialize_schema, upsert_vault
from llm_wiki.core.scanner import scan_vault_sources
from llm_wiki.core.secrets import load_groq_api_key, save_groq_api_key
from llm_wiki.core.vault import initialize_vault
from llm_wiki.retrieval.qa import answer_question, render_qa_markdown
from llm_wiki.ui.dashboard import build_dashboard_data, render_dashboard_text


def main() -> int:
    try:
        from PySide6.QtWidgets import (
            QApplication,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for GUI mode.") from exc

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Local LLM Wiki")
            self.resize(1040, 720)
            self.vault_root: Path | None = None
            self.config: AppConfig | None = None

            central = QWidget()
            layout = QVBoxLayout()

            top = QHBoxLayout()
            self.vault_label = QLabel("Vault: (not selected)")
            btn_pick = QPushButton("Select Vault")
            btn_pick.clicked.connect(self.select_vault)
            top.addWidget(self.vault_label)
            top.addWidget(btn_pick)
            layout.addLayout(top)

            row_actions = QHBoxLayout()
            self.btn_ping = QPushButton("Provider Ping")
            self.btn_scan = QPushButton("Scan")
            self.btn_dashboard = QPushButton("Refresh Dashboard")
            row_actions.addWidget(self.btn_ping)
            row_actions.addWidget(self.btn_scan)
            row_actions.addWidget(self.btn_dashboard)
            self.btn_ping.clicked.connect(self.provider_ping_clicked)
            self.btn_scan.clicked.connect(self.scan_clicked)
            self.btn_dashboard.clicked.connect(self.dashboard_clicked)
            layout.addLayout(row_actions)

            row_ask = QHBoxLayout()
            self.ask_input = QLineEdit()
            self.ask_input.setPlaceholderText("Ask a question about processed notes...")
            self.btn_ask = QPushButton("Ask")
            self.btn_ask.clicked.connect(self.ask_clicked)
            row_ask.addWidget(self.ask_input)
            row_ask.addWidget(self.btn_ask)
            layout.addLayout(row_ask)

            self.output = QTextEdit()
            self.output.setReadOnly(True)
            layout.addWidget(self.output)

            central.setLayout(layout)
            self.setCentralWidget(central)

        def select_vault(self) -> None:
            path_str = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault")
            if not path_str:
                return
            vault_root = Path(path_str).resolve()
            layout = initialize_vault(vault_root)
            config = load_config(layout.config_path)
            if not config.groq_api_key:
                config.groq_api_key = load_groq_api_key(layout.metadata_dir)
            elif config.groq_api_key:
                save_groq_api_key(layout.metadata_dir, config.groq_api_key)
            if not config.vault_path:
                config = AppConfig(
                    vault_path=str(vault_root),
                    provider=config.provider,
                    model=config.model,
                    groq_api_key=config.groq_api_key,
                    groq_base_url=config.groq_base_url,
                    auto_process=config.auto_process,
                    git_integration_enabled=config.git_integration_enabled,
                )
                save_config(config, layout.config_path)
            self.vault_root = vault_root
            self.config = config
            self.vault_label.setText(f"Vault: {vault_root}")
            self.output.setPlainText("Vault selected.\nUse Scan or Refresh Dashboard.")

        def provider_ping_clicked(self) -> None:
            if not self.ensure_context():
                return
            provider = build_provider(self.config)
            ok, latency_ms, detail = provider_ping(provider)
            if ok:
                self.output.append(f"\nProvider ping OK ({provider.provider_name()}): {latency_ms:.1f}ms")
            else:
                self.output.append(f"\nProvider ping FAILED ({provider.provider_name()}): {latency_ms:.1f}ms {detail}")

        def scan_clicked(self) -> None:
            if not self.ensure_context():
                return
            provider = build_provider(self.config)
            db = Database(self.vault_root / ".llm-wiki" / "app.db")
            processed = 0
            with db.connect() as connection:
                initialize_schema(connection)
                vault_id = upsert_vault(connection, self.vault_root)
                for scanned_file in scan_vault_sources(self.vault_root):
                    process_scanned_file(
                        connection=connection,
                        vault_id=vault_id,
                        scanned_file=scanned_file,
                        provider=provider,
                        config=self.config,
                        vault_root=self.vault_root,
                    )
                    processed += 1
            self.output.append(f"\nScan complete. Processed candidates: {processed}")

        def dashboard_clicked(self) -> None:
            if not self.ensure_context():
                return
            db = Database(self.vault_root / ".llm-wiki" / "app.db")
            with db.connect() as connection:
                initialize_schema(connection)
                upsert_vault(connection, self.vault_root)
                data = build_dashboard_data(
                    connection=connection,
                    config=self.config,
                    vault_root=self.vault_root,
                )
                self.output.setPlainText(render_dashboard_text(data))

        def ask_clicked(self) -> None:
            if not self.ensure_context():
                return
            question = self.ask_input.text().strip()
            if not question:
                return
            db = Database(self.vault_root / ".llm-wiki" / "app.db")
            with db.connect() as connection:
                initialize_schema(connection)
                result = answer_question(connection, self.vault_root, question)
            self.output.setPlainText(render_qa_markdown(result))

        def ensure_context(self) -> bool:
            if self.vault_root is None or self.config is None:
                QMessageBox.warning(self, "Vault required", "Select an Obsidian vault first.")
                return False
            return True

    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
