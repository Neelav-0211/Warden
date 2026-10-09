from common.errors import WardenError


class NoCapableProviderError(WardenError):
    """Raised when no configured provider meets the requested capabilities."""

    code = "no_capable_model_provider"
