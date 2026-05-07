class VaultValidationError(ValueError):
    pass


class ConfigError(ValueError):
    pass


class SecretStorageError(RuntimeError):
    pass


class LLMOutputError(ValueError):
    pass


class WikiGenerationError(RuntimeError):
    pass
