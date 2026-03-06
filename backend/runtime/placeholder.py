from __future__ import annotations

from typing import Any, Iterator

from backend.config.schema import RuntimeConfig

from .interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatMessage,
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

    def _active_model(self) -> str | None:
        enabled = self._enabled_models()
        if self._config.default_model:
            for model in enabled:
                if model.id == self._config.default_model:
                    return model.id
        return enabled[0].id if enabled else None

    def get_status(self) -> RuntimeStatus:
        ready = self._started
        return RuntimeStatus(
            state="ready" if ready else "stopped",
            provider="placeholder",
            mode="placeholder",
            initialized=self._started,
            ready=ready,
            generation_ready=ready,
            provider_reachable=ready,
            active_model=self._active_model(),
            models_available=[model.id for model in self._enabled_models()],
            details={
                "generation_capable": ready,
                "real_inference": False,
                "reason": "Placeholder runtime active for deterministic local development flow.",
            },
        )

    def list_models(self) -> list[ModelInfo]:
        return self._enabled_models()

    def list_configured_models(self) -> list[ModelInfo]:
        return self._registry

    def get_metadata(self) -> dict[str, Any]:
        return {
            "provider": "placeholder",
            "supports_chat": True,
            "supports_embeddings": False,
            "supports_streaming": False,
            "mode": "placeholder",
        }

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        if not self._started:
            raise RuntimeUnavailableError("Placeholder runtime is not started.")

        model_lookup = {model.id: model for model in self._enabled_models()}
        if request.model not in model_lookup:
            raise RuntimeInvocationError(f"Model '{request.model}' is not enabled in placeholder runtime.")

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

    def stream_chat(self, request: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        raise NotImplementedError("Streaming is deferred to a later week.")

    def generate_embeddings(self, inputs: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embeddings generation is deferred to a later week.")
