"""Safe, typed errors for read-only upstream adapter calls."""

from __future__ import annotations


class AdapterReadError(RuntimeError):
    """An upstream read did not return usable evidence."""

    code = "adapter_read_error"


class AdapterUnavailableError(AdapterReadError):
    """The upstream could not be reached or is temporarily unavailable."""

    code = "adapter_unavailable"


class AdapterResponseError(AdapterReadError):
    """The upstream returned a non-success or malformed response."""

    code = "adapter_invalid_response"


class AdapterConfigurationError(AdapterReadError):
    """Required read-only upstream verification settings are missing."""

    code = "adapter_not_configured"
