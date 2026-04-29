from __future__ import annotations

import json
from pathlib import Path


SERVICE_NAME = "local-llm-wiki"
ACCOUNT_NAME_GROQ = "groq_api_key"
FALLBACK_FILENAME = "secrets.local.json"


def load_groq_api_key(metadata_dir: Path) -> str | None:
    keyring_value = _load_from_keyring()
    if keyring_value:
        return keyring_value
    return _load_from_fallback_file(metadata_dir)


def save_groq_api_key(metadata_dir: Path, api_key: str) -> None:
    if not api_key:
        return
    if _save_to_keyring(api_key):
        return
    _save_to_fallback_file(metadata_dir, api_key)


def _load_from_keyring() -> str | None:
    try:
        import keyring  # type: ignore
    except Exception:
        return None
    try:
        return keyring.get_password(SERVICE_NAME, ACCOUNT_NAME_GROQ)
    except Exception:
        return None


def _save_to_keyring(api_key: str) -> bool:
    try:
        import keyring  # type: ignore
    except Exception:
        return False
    try:
        keyring.set_password(SERVICE_NAME, ACCOUNT_NAME_GROQ, api_key)
        return True
    except Exception:
        return False


def _fallback_path(metadata_dir: Path) -> Path:
    return metadata_dir / FALLBACK_FILENAME


def _load_from_fallback_file(metadata_dir: Path) -> str | None:
    path = _fallback_path(metadata_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = payload.get(ACCOUNT_NAME_GROQ)
    return value if isinstance(value, str) and value else None


def _save_to_fallback_file(metadata_dir: Path, api_key: str) -> None:
    path = _fallback_path(metadata_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {ACCOUNT_NAME_GROQ: api_key}
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
