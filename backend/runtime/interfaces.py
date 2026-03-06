from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol


class RuntimeUnavailableError(RuntimeError):
    """Raised when runtime is not ready or temporarily unavailable."""


class RuntimeInvocationError(RuntimeError):
    """Raised when runtime call fails due to provider or payload issues."""


@dataclass
class RuntimeStatus:
    state: str
    provider: str
    mode: str
    initialized: bool
    ready: bool
    generation_ready: bool
    embedding_ready: bool
    provider_reachable: bool
    active_model: str | None
    models_available: list[str]
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "portable-ai-drive"
    role: str = "general"
    enabled: bool = True
    provider_model_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatGenerationRequest:
    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    request_id: str | None = None
    session_id: str | None = None


@dataclass(frozen=True)
class ChatGenerationChoice:
    index: int
    message: ChatMessage
    finish_reason: str


@dataclass(frozen=True)
class ChatGenerationResponse:
    model: str
    choices: list[ChatGenerationChoice]
    usage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingGenerationRequest:
    model: str
    input_texts: list[str]
    encoding_format: str | None = None
    user: str | None = None
    request_id: str | None = None


@dataclass(frozen=True)
class EmbeddingVector:
    index: int
    embedding: list[float]


@dataclass(frozen=True)
class EmbeddingGenerationResponse:
    model: str
    data: list[EmbeddingVector]
    usage: dict[str, int] = field(default_factory=dict)


class RuntimeBackend(Protocol):
    def startup(self) -> None:
        """Initialize runtime backend resources."""

    def shutdown(self) -> None:
        """Release runtime backend resources."""

    def get_status(self) -> RuntimeStatus:
        """Return current backend status."""

    def list_models(self) -> list[ModelInfo]:
        """Return currently available model descriptors for API usage."""

    def list_configured_models(self) -> list[ModelInfo]:
        """Return configured model registry entries, including disabled entries."""

    def get_metadata(self) -> dict[str, Any]:
        """Return runtime backend metadata."""

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        """Generate chat output for a complete non-streaming response."""

    def stream_chat(self, request: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        """Yield chat tokens/chunks for future streaming support."""

    def generate_embeddings(self, request: EmbeddingGenerationRequest) -> EmbeddingGenerationResponse:
        """Generate embedding vectors for one or more input strings."""
