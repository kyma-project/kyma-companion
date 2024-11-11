class ModelNotFoundError(Exception):
    """Raised when a requested model is not found in configuration."""


class UnsupportedModelError(Exception):
    """Raised when a model type is not supported."""
