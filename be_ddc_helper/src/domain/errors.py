class LLMOutputParseError(Exception):
    """Raised when the LLM response cannot be parsed into a SectionPlan."""


class LLMAuthError(Exception):
    """Raised when an API key is rejected by the provider."""


class ProviderNotConfiguredError(Exception):
    """Raised when no API key has been registered for a given provider."""


class BridgeNotConnectedError(Exception):
    """Raised when the browser extension has no active WebSocket connection."""


class BridgeTimeoutError(Exception):
    """Raised when the extension does not respond to a command within the timeout."""
