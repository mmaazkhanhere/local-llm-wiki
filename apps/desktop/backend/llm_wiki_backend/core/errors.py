class VaultValidationError(ValueError):
    pass


class ConfigError(ValueError):
    pass


class SecretStorageError(RuntimeError):
    pass
