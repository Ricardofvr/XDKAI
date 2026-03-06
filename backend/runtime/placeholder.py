from __future__ import annotations

import hashlib
from typing import Any, Iterator

from backend.config.schema import RuntimeConfig

from .interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatMessage,
    EmbeddingGenerationRequest,
    EmbeddingGenerationResponse,
    EmbeddingVector,
    ModelInfo,
    RuntimeInvocationError,
    RuntimeStatus,
    RuntimeUnavailableError,
)


class PlaceholderRuntime:
    """Fallback placeholder runtime with deterministic responses."""

    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config
        self._started = False
        self._registry = self._build_model_registry(config)

    def _build_model_registry(self, config: RuntimeConfig) -> list[ModelInfo]:
        registry: list[ModelInfo] = []
        for model in config.models:
            registry.append(
                ModelInfo(
                    id=model.public_name,
                    owned_by="portable-ai-drive-placeholder",
                    role=model.role,
                    enabled=model.enabled,
                    provider_model_id=model.provider_model_id,
                    metadata={**model.metadata, "runtime_mode": "placeholder"},
                )
            )
        return registry

    def startup(self) -> None:
        self._started = True

    def shutdown(self) -> None:
        self._started = False

    def _enabled_models(self) -> list[ModelInfo]:
        return [model for model in self._registry if model.enabled]

    def _enabled_generation_models(self) -> list[ModelInfo]:
        return [model for model in self._enabled_models() if model.role in {"general", "coder"}]

    def _enabled_embedding_models(self) -> list[ModelInfo]:
        return [model for model in self._enabled_models() if model.role == "embedding"]

    def _active_generation_model(self) -> str | None:
        enabled = self._enabled_generation_models()
        if self._config.default_model:
            for model in enabled:
                if model.id == self._config.default_model:
                    return model.id
        return enabled[0].id if enabled else None

    def _active_embedding_model(self) -> str | None:
        enabled = self._enabled_embedding_models()
        if self._config.default_embedding_model:
            for model in enabled:
                if model.id == self._config.default_embedding_model:
                    return model.id
        return enabled[0].id if enabled else None

    def get_status(self) -> RuntimeStatus:
        generation_ready = self._started and bool(self._enabled_generation_models())
        embedding_ready = self._started and bool(self._enabled_embedding_models())
        ready = generation_ready or embedding_ready

        return RuntimeStatus(
            state="ready" if ready else ("stopped" if not self._started else "degraded"),
            provider="placeholder",
            mode="placeholder",
            initialized=self._started,
            ready=ready,
            generation_ready=generation_ready,
            embedding_ready=embedding_ready,
            provider_reachable=self._started,
            active_model=self._active_generation_model() or self._active_embedding_model(),
            models_available=[model.id for model in self._enabled_models()],
            details={
                "generation_capable": generation_ready,
                "embedding_capable": embedding_ready,
                "real_inference": False,
                "reason": "Placeholder runtime active for deterministic local development flow.",
            },
        )

    def list_models(self) -> list[ModelInfo]:
        return self._enabled_models()

    def list_configured_models(self) -> list[ModelInfo]:
        return self._registry

    def get_metadata(self) -> dict[str, Any]:
        status = self.get_status()
        return {
            "provider": "placeholder",
            "supports_chat": True,
            "supports_embeddings": True,
            "supports_streaming": False,
            "mode": "placeholder",
            "generation_ready": status.generation_ready,
            "embedding_ready": status.embedding_ready,
        }

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        if not self._started:
            raise RuntimeUnavailableError("Placeholder runtime is not started.")

        model_lookup = {model.id: model for model in self._enabled_generation_models()}
        if request.model not in model_lookup:
            raise RuntimeInvocationError(f"Model '{request.model}' is not enabled for chat in placeholder runtime.")

        user_messages = [message.content for message in request.messages if message.role == "user"]
        last_user_content = user_messages[-1] if user_messages else ""

        content = (
            f"[placeholder-runtime] model={request.model}; "
            f"echo={last_user_content if last_user_content else 'no-user-message'}"
        )

        return ChatGenerationResponse(
            model=request.model,
            choices=[
                ChatGenerationChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=content),
                    finish_reason="stop",
                )
            ],
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )

    def _deterministic_embedding(self, text: str, dims: int = 16) -> list[float]:
        raw = hashlib.sha256(text.encode("utf-8")).digest()
        vector: list[float] = []
        for i in range(dims):
            byte = raw[i % len(raw)]
            # Map byte range [0,255] to float range [-1, 1]
            vector.append((byte / 127.5) - 1.0)
        return vector

    def generate_embeddings(self, request: EmbeddingGenerationRequest) -> EmbeddingGenerationResponse:
        if not self._started:
            raise RuntimeUnavailableError("Placeholder runtime is not started.")

        model_lookup = {model.id: model for model in self._enabled_embedding_models()}
        if request.model not in model_lookup:
            raise RuntimeInvocationError(
                f"Model '{request.model}' is not enabled for embeddings in placeholder runtime."
            )

        vectors = [EmbeddingVector(index=i, embedding=self._deterministic_embedding(text)) for i, text in enumerate(request.input_texts)]

        return EmbeddingGenerationResponse(
            model=request.model,
            data=vectors,
            usage={
                "prompt_tokens": 0,
                "total_tokens": 0,
            },
        )

    def stream_chat(self, request: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        raise NotImplementedError("Streaming is deferred to a later week.")
