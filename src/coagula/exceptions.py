"""
Type-safe error hierarchy for coagula.

All exceptions raised by the library inherit from ``CoagulaError``, enabling
callers to catch a single base type when needed.
"""


class CoagulaError(Exception):
    """Base exception for all coagula errors."""


class ValidationError(CoagulaError):
    """Raised when input data or a tool-call payload fails validation."""


class ExecutionError(CoagulaError):
    """Raised when the Speckit pipeline execution fails."""


class ConfigurationError(CoagulaError):
    """Raised when the SpeckitEngine is misconfigured (e.g. missing API key)."""


class RetryExhaustedError(CoagulaError):
    """Raised when all internal retry attempts have been exhausted."""