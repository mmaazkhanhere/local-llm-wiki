from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


CONFIG_FILENAME = "config.json"
APP_METADATA_DIRNAME = ".llm-wiki"


@dataclass
class AppConfig:
    vault_path: str | None = None
    provider: str = "groq"
    model: str = "configured-default"
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    auto_process: bool = True
    git_integration_enabled: bool = False


def metadata_dir_for_vault(vault_path: Path) -> Path:
    return vault_path / APP_METADATA_DIRNAME


def config_path_for_vault(vault_path: Path) -> Path:
    return metadata_dir_for_vault(vault_path) / CONFIG_FILENAME


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        return AppConfig()
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    # Ignore unexpected config keys so schema changes are backward compatible.
    allowed = set(AppConfig.__dataclass_fields__.keys())
    payload = {key: value for key, value in payload.items() if key in allowed}
    return AppConfig(**payload)


def save_config(config: AppConfig, config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(asdict(config), handle, indent=2, ensure_ascii=True)
