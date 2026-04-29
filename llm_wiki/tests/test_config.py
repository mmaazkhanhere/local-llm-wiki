from pathlib import Path

from llm_wiki.core.config import AppConfig, load_config, save_config


def test_config_round_trip(tmp_path: Path) -> None:
    config_path = tmp_path / ".llm-wiki" / "config.json"
    config = AppConfig(vault_path=str(tmp_path), provider="groq", model="foo")
    save_config(config, config_path)

    loaded = load_config(config_path)
    assert loaded.vault_path == str(tmp_path)
    assert loaded.provider == "groq"
    assert loaded.model == "foo"


def test_load_config_default_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / ".llm-wiki" / "config.json"
    loaded = load_config(missing)
    assert loaded.vault_path is None
    assert loaded.provider == "groq"
