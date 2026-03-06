from __future__ import annotations

import json
import logging
import socket
import time
from typing import Any, Iterator
from urllib import error, request

from backend.config.schema import RuntimeConfig

from ..interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatMessage,
    ModelInfo,
    RuntimeInvocationError,
    RuntimeStatus,
    RuntimeUnavailableError,
)


class LocalOpenAIRuntime:
    """Runtime adapter for a local OpenAI-compatible provider (e.g., llama.cpp server)."""

    def __init__(self, config: RuntimeConfig, logger: logging.Logger) -> None:
        self._config = config
        self._provider_cfg = config.local_openai
        self._logger = logger

        self._started = False
        self._provider_reachable = False
        self._generation_ready = False
        self._startup_error: str | None = None
        self._provider_models: set[str] = set()
        self._last_chat_error: str | None = None
        self._last_chat_latency_ms: int | None = None
        self._registry = self._build_model_registry(config)

    def _build_model_registry(self, config: RuntimeConfig) -> list[ModelInfo]:
        registry: list[ModelInfo] = []
        for model in config.models:
            registry.append(
                ModelInfo(
                    id=model.public_name,
                    owned_by="portable-ai-drive-local-runtime",
                    role=model.role,
                    enabled=model.enabled,
                    provider_model_id=model.provider_model_id,
                    metadata=dict(model.metadata),
                )
            )
        return registry

    def _enabled_models(self) -> list[ModelInfo]:
        return [model for model in self._registry if model.enabled]

    def _active_model(self) -> str | None:
        enabled = self._enabled_models()
        if self._config.default_model:
            for model in enabled:
                if model.id == self._config.default_model:
                    return model.id
        return enabled[0].id if enabled else None

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._provider_cfg.base_url}{path}"

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = self._url(path)
        headers = {"Accept": "application/json"}
        body: bytes | None = None

        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url=url, data=body, headers=headers, method=method)

        try:
            with request.urlopen(req, timeout=self._provider_cfg.timeout_seconds) as response:
                raw = response.read()
        except error.HTTPError as exc:
            provider_message = f"HTTP {exc.code}"
            try:
                error_raw = exc.read()
                if error_raw:
                    parsed = json.loads(error_raw.decode("utf-8"))
                    if isinstance(parsed, dict):
                        error_obj = parsed.get("error")
                        if isinstance(error_obj, dict):
                            message = error_obj.get("message")
                            if isinstance(message, str) and message:
                                provider_message = message
                        elif isinstance(parsed.get("message"), str):
                            provider_message = parsed["message"]
            except Exception:  # noqa: BLE001
                provider_message = f"HTTP {exc.code}"

            raise RuntimeInvocationError(
                f"Local runtime HTTP {exc.code} for {url}: {provider_message}"
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeUnavailableError(
                f"Local runtime request timed out after {self._provider_cfg.timeout_seconds}s: {url}"
            ) from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", str(exc))
            raise RuntimeUnavailableError(f"Unable to reach local runtime at {url}: {reason}") from exc
        except OSError as exc:
            raise RuntimeUnavailableError(f"Local runtime connection failed for {url}: {exc}") from exc

        if not raw:
            return {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeInvocationError(f"Local runtime returned non-JSON payload for {url}.") from exc

        if not isinstance(parsed, dict):
            raise RuntimeInvocationError(f"Local runtime response for {url} must be a JSON object.")

        return parsed

    def _probe_health(self) -> None:
        url = self._url(self._provider_cfg.health_path)
        req = request.Request(url=url, method="GET")
        try:
            with request.urlopen(req, timeout=self._provider_cfg.timeout_seconds):
                return
        except error.HTTPError:
            # Any HTTP response means endpoint is reachable. Health semantics are provider-specific.
            return
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeUnavailableError(
                f"Local runtime request timed out after {self._provider_cfg.timeout_seconds}s: {url}"
            ) from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", str(exc))
            raise RuntimeUnavailableError(f"Unable to reach local runtime at {url}: {reason}") from exc
        except OSError as exc:
            raise RuntimeUnavailableError(f"Local runtime connection failed for {url}: {exc}") from exc

    def _refresh_provider_models(self) -> None:
        payload = self._request_json("GET", self._provider_cfg.models_path)
        models = payload.get("data")
        if not isinstance(models, list):
            raise RuntimeInvocationError("Local runtime models response missing 'data' array.")

        detected: set[str] = set()
        for entry in models:
            if isinstance(entry, dict):
                model_id = entry.get("id")
                if isinstance(model_id, str) and model_id:
                    detected.add(model_id)

        self._provider_models = detected

    def _evaluate_generation_readiness(self) -> tuple[bool, str]:
        enabled_models = self._enabled_models()
        if not enabled_models:
            return False, "No enabled models in runtime registry."

        if not self._provider_models:
            return False, "Provider returned no models."

        for model in enabled_models:
            if model.provider_model_id in self._provider_models:
                return True, "At least one enabled registry model is available in provider model list."

        return False, "No enabled registry model is available in provider model list."

    def startup(self) -> None:
        self._started = True
        self._provider_reachable = False
        self._generation_ready = False
        self._startup_error = None

        try:
            self._probe_health()
            self._provider_reachable = True
            self._refresh_provider_models()
            generation_ready, generation_reason = self._evaluate_generation_readiness()
            self._generation_ready = generation_ready

            if not self._generation_ready:
                self._startup_error = generation_reason
                self._logger.warning(
                    "local_openai_runtime_degraded",
                    extra={
                        "event": "runtime_provider",
                        "provider": "local_openai",
                        "base_url": self._provider_cfg.base_url,
                        "reason": generation_reason,
                        "detected_provider_models": sorted(self._provider_models),
                    },
                )
            else:
                self._logger.info(
                    "local_openai_runtime_ready",
                    extra={
                        "event": "runtime_provider",
                        "provider": "local_openai",
                        "base_url": self._provider_cfg.base_url,
                        "detected_provider_models": sorted(self._provider_models),
                    },
                )
        except (RuntimeUnavailableError, RuntimeInvocationError) as exc:
            self._startup_error = str(exc)
            self._provider_reachable = False
            self._generation_ready = False
            self._logger.warning(
                "local_openai_runtime_unavailable",
                extra={
                    "event": "runtime_provider",
                    "provider": "local_openai",
                    "base_url": self._provider_cfg.base_url,
                    "error": self._startup_error,
                },
            )

    def shutdown(self) -> None:
        self._started = False
        self._provider_reachable = False
        self._generation_ready = False

    def get_status(self) -> RuntimeStatus:
        if not self._started:
            state = "stopped"
        elif self._generation_ready:
            state = "ready"
        else:
            state = "degraded"

        enabled_models = self._enabled_models()
        models_available = [model.id for model in enabled_models]

        return RuntimeStatus(
            state=state,
            provider="local_openai",
            mode="provider",
            initialized=self._started,
            ready=self._generation_ready,
            generation_ready=self._generation_ready,
            provider_reachable=self._provider_reachable,
            active_model=self._active_model(),
            models_available=models_available,
            details={
                "base_url": self._provider_cfg.base_url,
                "provider_health_path": self._provider_cfg.health_path,
                "provider_models_path": self._provider_cfg.models_path,
                "detected_provider_models": sorted(self._provider_models),
                "configured_enabled_models": [model.id for model in enabled_models],
                "generation_capable": self._generation_ready,
                "startup_error": self._startup_error,
                "last_chat_error": self._last_chat_error,
                "last_chat_latency_ms": self._last_chat_latency_ms,
            },
        )

    def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        for model in self._enabled_models():
            provider_available = model.provider_model_id in self._provider_models
            metadata = {
                **model.metadata,
                "provider_available": provider_available,
                "provider": "local_openai",
                "generation_ready": self._generation_ready,
            }
            models.append(
                ModelInfo(
                    id=model.id,
                    object=model.object,
                    created=model.created,
                    owned_by=model.owned_by,
                    role=model.role,
                    enabled=model.enabled,
                    provider_model_id=model.provider_model_id,
                    metadata=metadata,
                )
            )
        return models

    def list_configured_models(self) -> list[ModelInfo]:
        return self._registry

    def get_metadata(self) -> dict[str, Any]:
        return {
            "provider": "local_openai",
            "supports_chat": True,
            "supports_embeddings": False,
            "supports_streaming": False,
            "mode": "provider",
            "base_url": self._provider_cfg.base_url,
            "generation_ready": self._generation_ready,
        }

    def _resolve_registry_model(self, requested_model: str) -> ModelInfo:
        for model in self._enabled_models():
            if model.id == requested_model and model.provider_model_id:
                return model
        raise RuntimeInvocationError(f"Model '{requested_model}' is not enabled in runtime registry.")

    def _ensure_provider_model_available(self, model: ModelInfo) -> None:
        if model.provider_model_id in self._provider_models:
            return

        self._refresh_provider_models()
        if model.provider_model_id not in self._provider_models:
            raise RuntimeInvocationError(
                f"Provider model '{model.provider_model_id}' for public model '{model.id}' is unavailable."
            )

    def _normalize_message_content(self, content_raw: Any) -> str:
        if isinstance(content_raw, str):
            return content_raw
        if content_raw is None:
            return ""
        if isinstance(content_raw, list):
            chunks: list[str] = []
            for item in content_raw:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
            if chunks:
                return "".join(chunks)
        raise RuntimeInvocationError("Local runtime returned unsupported message content format.")

    def _coerce_non_negative_int(self, value: Any) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value if value >= 0 else 0
        if isinstance(value, str):
            try:
                parsed = int(value)
                return parsed if parsed >= 0 else 0
            except ValueError:
                return 0
        return 0

    def generate_chat(self, request_data: ChatGenerationRequest) -> ChatGenerationResponse:
        if not self._started or not self._provider_reachable:
            raise RuntimeUnavailableError("Local runtime provider is unreachable.")

        registry_model = self._resolve_registry_model(request_data.model)
        try:
            self._ensure_provider_model_available(registry_model)

            payload: dict[str, Any] = {
                "model": registry_model.provider_model_id,
                "messages": [{"role": message.role, "content": message.content} for message in request_data.messages],
                "stream": False,
            }
            if request_data.temperature is not None:
                payload["temperature"] = request_data.temperature
            if request_data.max_tokens is not None:
                payload["max_tokens"] = request_data.max_tokens

            started = time.monotonic()
            response_payload = self._request_json("POST", self._provider_cfg.chat_completions_path, payload=payload)
            latency_ms = int((time.monotonic() - started) * 1000)

            choices_raw = response_payload.get("choices")
            if not isinstance(choices_raw, list) or not choices_raw:
                raise RuntimeInvocationError("Local runtime chat response missing non-empty 'choices' array.")

            first_choice = choices_raw[0]
            if not isinstance(first_choice, dict):
                raise RuntimeInvocationError("Local runtime chat choice payload is invalid.")

            role = "assistant"
            content = ""

            message_obj = first_choice.get("message")
            if isinstance(message_obj, dict):
                role_raw = message_obj.get("role")
                content_raw = message_obj.get("content")
                if isinstance(role_raw, str) and role_raw:
                    role = role_raw
                content = self._normalize_message_content(content_raw)
            elif isinstance(first_choice.get("text"), str):
                content = first_choice["text"]
            else:
                raise RuntimeInvocationError("Local runtime chat choice missing supported message payload.")

            finish_reason = first_choice.get("finish_reason", "stop")
            if not isinstance(finish_reason, str):
                finish_reason = "stop"

            usage_raw = response_payload.get("usage", {})
            usage = {
                "prompt_tokens": self._coerce_non_negative_int(usage_raw.get("prompt_tokens", 0))
                if isinstance(usage_raw, dict)
                else 0,
                "completion_tokens": self._coerce_non_negative_int(usage_raw.get("completion_tokens", 0))
                if isinstance(usage_raw, dict)
                else 0,
                "total_tokens": self._coerce_non_negative_int(usage_raw.get("total_tokens", 0))
                if isinstance(usage_raw, dict)
                else 0,
            }

            self._last_chat_error = None
            self._last_chat_latency_ms = latency_ms
            self._generation_ready = True

            self._logger.info(
                "local_openai_chat_completed",
                extra={
                    "event": "runtime_provider",
                    "provider": "local_openai",
                    "public_model": request_data.model,
                    "provider_model_id": registry_model.provider_model_id,
                    "latency_ms": latency_ms,
                    "request_id": request_data.request_id,
                },
            )

            return ChatGenerationResponse(
                model=request_data.model,
                choices=[
                    ChatGenerationChoice(
                        index=first_choice.get("index", 0) if isinstance(first_choice.get("index", 0), int) else 0,
                        message=ChatMessage(role=role, content=content),
                        finish_reason=finish_reason,
                    )
                ],
                usage=usage,
            )
        except (RuntimeInvocationError, RuntimeUnavailableError) as exc:
            self._last_chat_error = str(exc)
            raise

    def stream_chat(self, request_data: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        raise NotImplementedError("Streaming is deferred to a later week.")

    def generate_embeddings(self, inputs: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embeddings generation is deferred to a later week.")
