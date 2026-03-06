from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Iterator

from .interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ModelInfo,
    RuntimeBackend,
    RuntimeStatus,
)


class RuntimeManager:
    """Application-facing runtime abstraction manager."""

    def __init__(self, backend: RuntimeBackend, logger: logging.Logger) -> None:
        self._backend = backend
        self._logger = logger

    def startup(self) -> None:
        self._logger.info(
            "runtime_initializing",
            extra={"event": "startup_step", "step": "runtime_initializing"},
        )
        self._backend.startup()
        self._logger.info(
            "runtime_initialized",
            extra={"event": "startup_step", "step": "runtime_initialized"},
        )

    def shutdown(self) -> None:
        self._backend.shutdown()
        self._logger.info("runtime_shutdown", extra={"event": "shutdown_step", "step": "runtime_shutdown"})

    def get_status(self) -> RuntimeStatus:
        return self._backend.get_status()

    def get_status_payload(self) -> dict[str, object]:
        return asdict(self.get_status())

    def get_metadata(self) -> dict[str, object]:
        return self._backend.get_metadata()

    def list_models(self) -> list[ModelInfo]:
        self._logger.info("runtime_list_models", extra={"event": "runtime_call", "operation": "list_models"})
        return self._backend.list_models()

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        self._logger.info(
            "runtime_generate_chat",
            extra={
                "event": "runtime_call",
                "operation": "generate_chat",
                "model": request.model,
                "stream": request.stream,
                "request_id": request.request_id,
            },
        )
        response = self._backend.generate_chat(request)
        self._logger.info(
            "runtime_generate_chat_complete",
            extra={
                "event": "runtime_call",
                "operation": "generate_chat_complete",
                "model": response.model,
                "request_id": request.request_id,
            },
        )
        return response

    def stream_chat(self, request: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        self._logger.info(
            "runtime_stream_chat",
            extra={
                "event": "runtime_call",
                "operation": "stream_chat",
                "model": request.model,
                "request_id": request.request_id,
            },
        )
        return self._backend.stream_chat(request)
