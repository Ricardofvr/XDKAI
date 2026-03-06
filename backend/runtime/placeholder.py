from __future__ import annotations

from typing import Any

from backend.config.schema import RuntimeConfig

from .interfaces import RuntimeStatus


class PlaceholderRuntime:
    """Week 2 runtime backend placeholder with no inference capability."""

    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config
        self._started = False

    def startup(self) -> None:
        self._started = True

    def shutdown(self) -> None:
        self._started = False

    def get_status(self) -> RuntimeStatus:
        return RuntimeStatus(
            state="ready" if self._started else "stopped",
            provider=self._config.provider,
            active_model=self._config.default_model,
            models_available=[],
            details={
                "inference_ready": False,
                "reason": "Runtime placeholder only. Real model integration deferred.",
            },
        )

    def list_models(self) -> list[str]:
        return []

    def get_metadata(self) -> dict[str, Any]:
        return {
            "provider": self._config.provider,
            "startup_timeout_seconds": self._config.startup_timeout_seconds,
            "supports_chat": False,
            "supports_embeddings": False,
        }

    def generate_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("Chat generation is deferred to a later week.")

    def generate_embeddings(self, inputs: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embeddings generation is deferred to a later week.")
