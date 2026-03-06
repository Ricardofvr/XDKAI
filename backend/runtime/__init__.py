"""Runtime abstraction and manager."""

from .factory import build_runtime_backends
from .interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatMessage,
    ModelInfo,
    RuntimeBackend,
    RuntimeInvocationError,
    RuntimeStatus,
    RuntimeUnavailableError,
)
from .manager import RuntimeManager
from .placeholder import PlaceholderRuntime

__all__ = [
    "ChatGenerationChoice",
    "ChatGenerationRequest",
    "ChatGenerationResponse",
    "ChatMessage",
    "ModelInfo",
    "RuntimeBackend",
    "RuntimeInvocationError",
    "RuntimeManager",
    "RuntimeStatus",
    "RuntimeUnavailableError",
    "PlaceholderRuntime",
    "build_runtime_backends",
]
