from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol


@dataclass
class RuntimeStatus:
    state: str
    provider: str
    active_model: str | None
    models_available: list[str]
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInfo:
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "portable-ai-drive"


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


class RuntimeBackend(Protocol):
    def startup(self) -> None:
        """Initialize runtime backend resources."""

    def shutdown(self) -> None:
        """Release runtime backend resources."""

    def get_status(self) -> RuntimeStatus:
        """Return current backend status."""

    def list_models(self) -> list[ModelInfo]:
        """Return currently known model descriptors."""

    def get_metadata(self) -> dict[str, Any]:
        """Return runtime backend metadata."""

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        """Generate chat output for a complete non-streaming response."""

    def stream_chat(self, request: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        """Yield chat tokens/chunks for future streaming support."""

    def generate_embeddings(self, inputs: list[str], **kwargs: Any) -> list[list[float]]:
        """Generate embeddings (not implemented in Week 3)."""
