from __future__ import annotations


class LLMWikiError(Exception):
    """Base application error."""


class TransientError(LLMWikiError):
    """Recoverable error that may succeed with retry."""


class PermanentError(LLMWikiError):
    """Non-recoverable error that should not be retried."""


class ProviderTransientError(TransientError):
    """Transient provider/network issue."""


class ProviderPermanentError(PermanentError):
    """Permanent provider/auth/request issue."""


class ExtractionTransientError(TransientError):
    """Temporary extraction/read issue."""


class ExtractionPermanentError(PermanentError):
    """Permanent extraction/parsing issue."""


class WritePathError(PermanentError):
    """Unsafe write-path or write scope violation."""
