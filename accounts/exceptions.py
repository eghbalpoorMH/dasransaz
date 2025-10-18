class VerificationError(Exception):
    """Base class for verification related errors."""


class CodeExpiredError(VerificationError):
    """Raised when a code has expired."""


class InvalidCodeError(VerificationError):
    """Raised when a code does not match."""
