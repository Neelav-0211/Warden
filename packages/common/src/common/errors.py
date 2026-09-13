class WardenError(Exception):
    """Base exception for errors with stable API-facing codes."""

    code = "warden_error"


class ConfigError(WardenError):
    """Raised when application configuration is invalid."""

    code = "config_error"


class NotFoundError(WardenError):
    """Raised when a requested resource does not exist."""

    code = "not_found"


class ExternalServiceError(WardenError):
    """Raised when an external service operation fails."""

    code = "external_service_error"
