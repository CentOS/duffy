class DuffyException(Exception):  # pragma: no cover
    """Custom exceptions for Duffy."""


class DuffyConfigurationError(DuffyException):  # pragma: no cover
    """Something's wrong with the configuration of Duffy."""


class DuffyShellUnavailableError(DuffyException):  # pragma: no cover
    """The selected interactive shell type is not available."""
