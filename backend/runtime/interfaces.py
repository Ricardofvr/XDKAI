from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RuntimeStatus:
    state: str
    provider: str
    active_model: str | None
    models_available: list[str]
    details: dict[str, Any] = field(default_factory=dict)


class RuntimeBackend(Protocol):
    def startup(self) -> None:
        """Initialize runtime backend resources."""

    def shutdown(self) -> None:
        """Release runtime backend resources."""

    def get_status(self) -> RuntimeStatus:
        """Return current backend status."""

    def list_models(self) -> list[str]:
        """Return currently known model identifiers."""

    def get_metadata(self) -> dict[str, Any]:
        """Return runtime backend metadata."""

    def generate_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Generate chat output (not implemented in Week 2)."""

    def generate_embeddings(self, inputs: list[str], **kwargs: Any) -> list[list[float]]:
        """Generate embeddings (not implemented in Week 2)."""
