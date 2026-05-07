from __future__ import annotations

import logging
import os
from typing import Final

from colorama import Fore, Style, init as colorama_init

_CONFIGURED: bool = False
_LOGGER_NAME: Final[str] = "llm_wiki_backend"


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname
        color = ""
        if record.levelno >= logging.ERROR:
            color = Fore.RED
        elif record.levelno >= logging.WARNING:
            color = Fore.YELLOW
        elif record.levelno >= logging.INFO:
            color = Fore.CYAN
        else:
            color = Fore.WHITE

        subsystem = record.name.replace(_LOGGER_NAME, "").lstrip(".") or "app"
        subsystem_color = Fore.MAGENTA
        if subsystem.startswith(("ingestion", "watcher")):
            subsystem_color = Fore.GREEN
        elif subsystem.startswith("api"):
            subsystem_color = Fore.BLUE
        elif subsystem.startswith("wiki"):
            subsystem_color = Fore.LIGHTMAGENTA_EX

        prefix = f"{color}{level:>7}{Style.RESET_ALL}"
        tag = f"{subsystem_color}[{subsystem}]{Style.RESET_ALL}"
        message = super().format(record)
        return f"{prefix} {tag} {message}"


def configure_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    colorama_init(strip=False)

    resolved_level = (level or os.getenv("LLM_WIKI_LOG_LEVEL") or "INFO").upper()
    numeric_level = getattr(logging, resolved_level, logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(numeric_level)
    handler.setFormatter(_ColorFormatter(fmt="%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"))

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(numeric_level)
    logger.handlers.clear()
    logger.propagate = False
    logger.addHandler(handler)

    for noisy in ("uvicorn.error", "uvicorn.access"):
        logging.getLogger(noisy).handlers.clear()
        logging.getLogger(noisy).propagate = True
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> logging.Logger:
    configure_logging()
    if not name:
        return logging.getLogger(_LOGGER_NAME)
    if name.startswith(_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
