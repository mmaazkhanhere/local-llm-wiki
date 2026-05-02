from __future__ import annotations

import base64
import json
from pathlib import Path

from llm_wiki_backend.core.errors import SecretStorageError

SERVICE_NAME = "local-llm-wiki"
KEY_NAME = "groq_api_key"


def save_groq_key(vault_path: Path, api_key: str) -> None:
    if _try_save_keyring(api_key):
        return
    _save_encrypted_fallback(vault_path, api_key)


def _try_save_keyring(api_key: str) -> bool:
    try:
        import keyring  # type: ignore

        keyring.set_password(SERVICE_NAME, KEY_NAME, api_key)
        return True
    except Exception:
        return False


def _save_encrypted_fallback(vault_path: Path, api_key: str) -> None:
    # This is intentionally lightweight fallback obfuscation for environments
    # without keychain support.
    payload = {"groq_api_key": base64.b64encode(api_key.encode("utf-8")).decode("ascii")}
    path = vault_path / ".llm-wiki" / "secrets.enc.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise SecretStorageError("Unable to persist provider key.") from exc
