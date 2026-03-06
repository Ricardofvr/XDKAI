from __future__ import annotations

from typing import Any, Iterator

from backend.config.schema import RuntimeConfig

from .interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatMessage,
    ModelInfo,
    RuntimeStatus,
)


class PlaceholderRuntime:
    """Week 3 placeholder runtime backend with deterministic mock chat output."""

    def __init__(self, config: RuntimeConfig) -> None:
        self._config = config
        self._started = False
        default_model = config.default_model or "padp-placeholder-chat-001"
        self._models = [ModelInfo(id=default_model)]

    def startup(self) -> None:
        self._started = True

    def shutdown(self) -> None:
        self._started = False

    def get_status(self) -> RuntimeStatus:
        return RuntimeStatus(
            state="ready" if self._started else "stopped",
            provider=self._config.provider,
            active_model=self._models[0].id,
            models_available=[model.id for model in self._models],
            details={
                "inference_ready": True,
                "reason": "Deterministic placeholder runtime active.",
            },
        )

    def list_models(self) -> list[ModelInfo]:
        return self._models

    def get_metadata(self) -> dict[str, Any]:
        return {
            "provider": self._config.provider,
            "startup_timeout_seconds": self._config.startup_timeout_seconds,
            "supports_chat": True,
            "supports_embeddings": False,
            "supports_streaming": False,
        }

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
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
