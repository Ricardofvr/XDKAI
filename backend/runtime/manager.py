from __future__ import annotations

import logging
import time
from dataclasses import asdict
from typing import Any, Iterator

from .interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ModelInfo,
    RuntimeBackend,
    RuntimeInvocationError,
    RuntimeStatus,
    RuntimeUnavailableError,
)


class RuntimeManager:
    """Application-facing runtime abstraction manager with provider lifecycle and fallback handling."""

    def __init__(
        self,
        primary_backend: RuntimeBackend,
        logger: logging.Logger,
        selected_provider: str,
        fallback_backend: RuntimeBackend | None = None,
        fallback_provider: str | None = None,
    ) -> None:
        self._primary_backend = primary_backend
        self._fallback_backend = fallback_backend
        self._active_backend: RuntimeBackend = primary_backend
        self._logger = logger
        self._selected_provider = selected_provider
        self._fallback_provider = fallback_provider
        self._fallback_engaged = False
        self._startup_errors: list[str] = []
        self._primary_status: RuntimeStatus | None = None

    def _start_backend(self, backend: RuntimeBackend, backend_label: str) -> RuntimeStatus:
        try:
            backend.startup()
        except Exception as exc:  # noqa: BLE001
            self._startup_errors.append(f"{backend_label} startup exception: {exc}")
            self._logger.exception(
                "runtime_backend_startup_exception",
                extra={
                    "event": "runtime_lifecycle",
                    "backend_label": backend_label,
                    "error": str(exc),
                },
            )

        try:
            status = backend.get_status()
        except Exception as exc:  # noqa: BLE001
            self._startup_errors.append(f"{backend_label} status exception: {exc}")
            self._logger.exception(
                "runtime_backend_status_exception",
                extra={
                    "event": "runtime_lifecycle",
                    "backend_label": backend_label,
                    "error": str(exc),
                },
            )
            status = RuntimeStatus(
                state="degraded",
                provider=self._selected_provider if backend_label == "primary" else (self._fallback_provider or "unknown"),
                mode="provider",
                initialized=True,
                ready=False,
                generation_ready=False,
                provider_reachable=False,
                active_model=None,
                models_available=[],
                details={"status_error": str(exc)},
            )

        return status

    def startup(self) -> None:
        self._logger.info(
            "runtime_provider_selected",
            extra={
                "event": "runtime_lifecycle",
                "selected_provider": self._selected_provider,
                "fallback_provider": self._fallback_provider,
            },
        )

        primary_status = self._start_backend(self._primary_backend, "primary")
        self._primary_status = primary_status
        self._active_backend = self._primary_backend

        if not primary_status.ready and self._fallback_backend is not None:
            self._logger.warning(
                "runtime_primary_unavailable_attempting_fallback",
                extra={
                    "event": "runtime_lifecycle",
                    "selected_provider": self._selected_provider,
                    "primary_state": primary_status.state,
                    "primary_details": primary_status.details,
                    "fallback_provider": self._fallback_provider,
                },
            )

            fallback_status = self._start_backend(self._fallback_backend, "fallback")
            if fallback_status.ready:
                self._active_backend = self._fallback_backend
                self._fallback_engaged = True
                self._logger.warning(
                    "runtime_fallback_engaged",
                    extra={
                        "event": "runtime_lifecycle",
                        "active_provider": fallback_status.provider,
                        "selected_provider": self._selected_provider,
                    },
                )
            else:
                self._logger.error(
                    "runtime_fallback_unavailable",
                    extra={
                        "event": "runtime_lifecycle",
                        "selected_provider": self._selected_provider,
                        "fallback_provider": self._fallback_provider,
                        "fallback_state": fallback_status.state,
                        "fallback_details": fallback_status.details,
                    },
                )

        active_status = self.get_status()
        self._logger.info(
            "runtime_initialized",
            extra={
                "event": "startup_step",
                "step": "runtime_initialized",
                "selected_provider": self._selected_provider,
                "active_provider": active_status.provider,
                "active_state": active_status.state,
                "fallback_engaged": self._fallback_engaged,
                "generation_ready": active_status.generation_ready,
            },
        )

    def shutdown(self) -> None:
        seen_backends: set[int] = set()
        for backend in [self._active_backend, self._primary_backend, self._fallback_backend]:
            if backend is None:
                continue
            backend_id = id(backend)
            if backend_id in seen_backends:
                continue
            seen_backends.add(backend_id)

            try:
                backend.shutdown()
            except Exception as exc:  # noqa: BLE001
                self._logger.warning(
                    "runtime_shutdown_error",
                    extra={"event": "shutdown_step", "step": "runtime_shutdown", "error": str(exc)},
                )

        self._logger.info("runtime_shutdown", extra={"event": "shutdown_step", "step": "runtime_shutdown"})

    def get_status(self) -> RuntimeStatus:
        return self._active_backend.get_status()

    def get_status_payload(self) -> dict[str, Any]:
        status = self.get_status()
        active_status = asdict(status)

        model_registry = self.get_model_registry_payload()
        active_status.update(
            {
                "selected_provider": self._selected_provider,
                "active_provider": active_status.get("provider"),
                "fallback_provider": self._fallback_provider,
                "fallback_engaged": self._fallback_engaged,
                "startup_errors": list(self._startup_errors),
                "primary_provider_status": asdict(self._primary_status) if self._primary_status else None,
                "generation": {
                    "generation_ready": status.generation_ready,
                    "provider_reachable": status.provider_reachable,
                    "model_registry_loaded": len(model_registry) > 0,
                    "enabled_models_count": len(status.models_available),
                    "active_model": status.active_model,
                    "mode": status.mode,
                },
            }
        )
        return active_status

    def get_metadata(self) -> dict[str, object]:
        status = self.get_status()
        metadata = self._active_backend.get_metadata()
        return {
            **metadata,
            "selected_provider": self._selected_provider,
            "fallback_provider": self._fallback_provider,
            "fallback_engaged": self._fallback_engaged,
            "generation_ready": status.generation_ready,
            "provider_reachable": status.provider_reachable,
        }

    def list_models(self) -> list[ModelInfo]:
        status = self.get_status()
        self._logger.info(
            "runtime_list_models",
            extra={
                "event": "runtime_call",
                "operation": "list_models",
                "active_provider": status.provider,
            },
        )
        return self._active_backend.list_models()

    def get_model_registry_payload(self) -> list[dict[str, Any]]:
        registry = self._active_backend.list_configured_models()
        return [
            {
                "public_name": model.id,
                "provider_model_id": model.provider_model_id,
                "role": model.role,
                "enabled": model.enabled,
                "metadata": model.metadata,
            }
            for model in registry
        ]

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        status = self.get_status()
        if not status.generation_ready:
            raise RuntimeUnavailableError(
                (
                    f"Runtime provider '{status.provider}' is not generation-ready "
                    f"(state={status.state}, provider_reachable={status.provider_reachable})."
                )
            )

        started = time.monotonic()
        self._logger.info(
            "runtime_generate_chat",
            extra={
                "event": "runtime_call",
                "operation": "generate_chat",
                "model": request.model,
                "stream": request.stream,
                "request_id": request.request_id,
                "active_provider": status.provider,
            },
        )

        try:
            response = self._active_backend.generate_chat(request)
        except RuntimeUnavailableError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            self._logger.warning(
                "runtime_generate_chat_failed",
                extra={
                    "event": "runtime_call",
                    "operation": "generate_chat_failed",
                    "request_id": request.request_id,
                    "active_provider": status.provider,
                    "error_type": "runtime_unavailable",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                },
            )
            raise
        except RuntimeInvocationError as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            self._logger.warning(
                "runtime_generate_chat_failed",
                extra={
                    "event": "runtime_call",
                    "operation": "generate_chat_failed",
                    "request_id": request.request_id,
                    "active_provider": status.provider,
                    "error_type": "runtime_invocation_error",
                    "error": str(exc),
                    "duration_ms": duration_ms,
                },
            )
            raise
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - started) * 1000)
            self._logger.exception(
                "runtime_generate_chat_exception",
                extra={
                    "event": "runtime_call",
                    "operation": "generate_chat_exception",
                    "request_id": request.request_id,
                    "active_provider": status.provider,
                    "duration_ms": duration_ms,
                },
            )
            raise RuntimeInvocationError(f"Unexpected runtime error: {exc}") from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        self._logger.info(
            "runtime_generate_chat_complete",
            extra={
                "event": "runtime_call",
                "operation": "generate_chat_complete",
                "model": response.model,
                "request_id": request.request_id,
                "active_provider": status.provider,
                "duration_ms": duration_ms,
            },
        )
        return response

    def stream_chat(self, request: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        status = self.get_status()
        self._logger.info(
            "runtime_stream_chat",
            extra={
                "event": "runtime_call",
                "operation": "stream_chat",
                "model": request.model,
                "request_id": request.request_id,
                "active_provider": status.provider,
            },
        )
        return self._active_backend.stream_chat(request)
