from __future__ import annotations

import base64
import json
from pathlib import Path

from llm_wiki_backend.core.errors import SecretStorageError

SERVICE_NAME = "local-llm-wiki"
LEGACY_KEY_NAME = "groq_api_key"
KEY_PREFIX = "groq_api_key::"


def save_groq_key(vault_path: Path, api_key: str) -> None:
    if _try_save_keyring(vault_path, api_key):
        return
    _save_encrypted_fallback(vault_path, api_key)


def has_groq_key(vault_path: Path) -> bool:
    if _try_has_keyring_key(vault_path):
        return True
    return _fallback_key_exists(vault_path)


def load_groq_key(vault_path: Path) -> str:
    keyring_value = _try_load_keyring_key(vault_path)
    if keyring_value:
        return keyring_value

    fallback_value = _load_fallback_key(vault_path)
    if fallback_value:
        return fallback_value

    raise SecretStorageError("Groq API key is not configured.")


def clear_groq_key(vault_path: Path) -> None:
    _try_delete_keyring(vault_path)
    path = vault_path / ".llm-wiki" / "secrets.enc.json"
    if path.exists():
        path.unlink(missing_ok=True)


def _scoped_key_name(vault_path: Path) -> str:
    return f"{KEY_PREFIX}{str(vault_path.resolve())}"


def _try_save_keyring(vault_path: Path, api_key: str) -> bool:
    try:
        import keyring  # type: ignore

        keyring.set_password(SERVICE_NAME, _scoped_key_name(vault_path), api_key)
        return True
    except Exception:
        return False


def _try_has_keyring_key(vault_path: Path) -> bool:
    try:
        import keyring  # type: ignore

        saved = keyring.get_password(SERVICE_NAME, _scoped_key_name(vault_path))
        return bool(saved)
    except Exception:
        return False


def _try_load_keyring_key(vault_path: Path) -> str | None:
    try:
        import keyring  # type: ignore

        saved = keyring.get_password(SERVICE_NAME, _scoped_key_name(vault_path))
    except Exception:
        return None
    if not saved:
        return None
    return saved


def _try_delete_keyring(vault_path: Path) -> None:
    try:
        import keyring  # type: ignore
        from keyring.errors import PasswordDeleteError  # type: ignore

        for key_name in (_scoped_key_name(vault_path), LEGACY_KEY_NAME):
            try:
                keyring.delete_password(SERVICE_NAME, key_name)
            except PasswordDeleteError:
                continue
    except Exception:
        return


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


def _fallback_key_exists(vault_path: Path) -> bool:
    return _load_fallback_key(vault_path) is not None


def _load_fallback_key(vault_path: Path) -> str | None:
    path = vault_path / ".llm-wiki" / "secrets.enc.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("groq_api_key")
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return base64.b64decode(value.encode("ascii")).decode("utf-8")
    except Exception:
        return None
