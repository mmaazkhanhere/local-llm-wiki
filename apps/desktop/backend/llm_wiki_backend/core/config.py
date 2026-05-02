from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from llm_wiki_backend.core.errors import ConfigError
from llm_wiki_backend.core.models import AppConfig


def config_path(vault_path: Path) -> Path:
    return vault_path / ".llm-wiki" / "config.json"


def load_config(vault_path: Path) -> AppConfig | None:
    path = config_path(vault_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid config JSON: {exc}") from exc
    try:
        return AppConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid config schema: {exc}") from exc


def save_config(config: AppConfig, vault_path: Path) -> Path:
    path = config_path(vault_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return path
