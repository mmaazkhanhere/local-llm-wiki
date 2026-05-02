from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    timestamp: str

    @classmethod
    def ok(cls, version: str) -> "HealthResponse":
        return cls(status="ok", version=version, timestamp=datetime.now(UTC).isoformat())


class SelectVaultRequest(BaseModel):
    path: str = Field(min_length=1)


class SelectVaultResponse(BaseModel):
    vault_path: str
    exists: bool
    is_directory: bool
    has_obsidian: bool
    warning: str | None = None


class BootstrapResponse(BaseModel):
    vault_path: str
    created_directories: list[str]
    created_files: list[str]
    database_path: str
    config_path: str


class ProviderSettings(BaseModel):
    provider: str = "groq"
    default_text_model: str = "openai/gpt-oss-120b"
    cheap_fast_model: str = "llama-3.1-8b-instant"
    review_model: str = "openai/gpt-oss-120b"
    vision_model: str | None = None


class AppConfig(BaseModel):
    vault_path: str
    provider: ProviderSettings = Field(default_factory=ProviderSettings)


class ConfigureVaultResponse(BaseModel):
    vault_path: str
    has_obsidian: bool
    git_detected: bool
    obsidian_cli_available: bool
    warning: str | None = None


class ProviderTestRequest(BaseModel):
    api_key: str = Field(min_length=1)


class ProviderTestResponse(BaseModel):
    provider: str = "groq"
    connected: bool
    message: str


class StatusResponse(BaseModel):
    vault_path: str
    has_obsidian: bool
    git_detected: bool
    obsidian_cli_available: bool
