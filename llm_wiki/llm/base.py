from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    model: str
    base_url: str


class LLMProvider(ABC):
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def supports_vision(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def validate_configuration(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_path: str,
        *,
        temperature: float = 0.2,
    ) -> str:
        raise NotImplementedError
