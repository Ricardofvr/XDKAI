from __future__ import annotations

import json
import logging
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
        self._ready = False
        self._startup_error: str | None = None
        self._provider_models: set[str] = set()
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
        except error.URLError as exc:
            raise RuntimeUnavailableError(f"Unable to reach local runtime at {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeUnavailableError(
                f"Local runtime request timed out after {self._provider_cfg.timeout_seconds}s: {url}"
            ) from exc
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
        except error.URLError as exc:
            raise RuntimeUnavailableError(f"Unable to reach local runtime at {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise RuntimeUnavailableError(
                f"Local runtime request timed out after {self._provider_cfg.timeout_seconds}s: {url}"
            ) from exc
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

    def startup(self) -> None:
        self._started = True
        self._ready = False
        self._startup_error = None

        try:
            # Probe health endpoint first, then model listing for readiness and availability.
            self._probe_health()
            self._refresh_provider_models()
            self._ready = True
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
            self._ready = False
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
        self._ready = False

    def get_status(self) -> RuntimeStatus:
        if not self._started:
            state = "stopped"
        elif self._ready:
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
            ready=self._ready,
            active_model=self._active_model(),
            models_available=models_available,
            details={
                "base_url": self._provider_cfg.base_url,
                "provider_health_path": self._provider_cfg.health_path,
                "provider_models_path": self._provider_cfg.models_path,
                "detected_provider_models": sorted(self._provider_models),
                "startup_error": self._startup_error,
            },
        )

    def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        for model in self._enabled_models():
            provider_available = model.provider_model_id in self._provider_models if self._provider_models else self._ready
            metadata = {
                **model.metadata,
                "provider_available": provider_available,
                "provider": "local_openai",
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
        }

    def _resolve_provider_model_id(self, requested_model: str) -> str:
        for model in self._enabled_models():
            if model.id == requested_model and model.provider_model_id:
                return model.provider_model_id
        raise RuntimeInvocationError(f"Model '{requested_model}' is not enabled for local runtime.")

    def generate_chat(self, request_data: ChatGenerationRequest) -> ChatGenerationResponse:
        if not self._started or not self._ready:
            raise RuntimeUnavailableError("Local runtime provider is not ready.")

        provider_model_id = self._resolve_provider_model_id(request_data.model)

        payload: dict[str, Any] = {
            "model": provider_model_id,
            "messages": [{"role": message.role, "content": message.content} for message in request_data.messages],
            "stream": False,
        }
        if request_data.temperature is not None:
            payload["temperature"] = request_data.temperature
        if request_data.max_tokens is not None:
            payload["max_tokens"] = request_data.max_tokens

        response_payload = self._request_json("POST", self._provider_cfg.chat_completions_path, payload=payload)

        choices_raw = response_payload.get("choices")
        if not isinstance(choices_raw, list) or not choices_raw:
            raise RuntimeInvocationError("Local runtime chat response missing non-empty 'choices' array.")

        first_choice = choices_raw[0]
        if not isinstance(first_choice, dict):
            raise RuntimeInvocationError("Local runtime chat choice payload is invalid.")

        message_obj = first_choice.get("message")
        if not isinstance(message_obj, dict):
            raise RuntimeInvocationError("Local runtime chat choice missing message object.")

        role = message_obj.get("role")
        content = message_obj.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise RuntimeInvocationError("Local runtime chat message fields are invalid.")

        finish_reason = first_choice.get("finish_reason", "stop")
        if not isinstance(finish_reason, str):
            finish_reason = "stop"

        usage_raw = response_payload.get("usage", {})
        usage = {
            "prompt_tokens": int(usage_raw.get("prompt_tokens", 0)) if isinstance(usage_raw, dict) else 0,
            "completion_tokens": int(usage_raw.get("completion_tokens", 0)) if isinstance(usage_raw, dict) else 0,
            "total_tokens": int(usage_raw.get("total_tokens", 0)) if isinstance(usage_raw, dict) else 0,
        }

        return ChatGenerationResponse(
            model=request_data.model,
            choices=[
                ChatGenerationChoice(
                    index=int(first_choice.get("index", 0)) if isinstance(first_choice.get("index", 0), int) else 0,
                    message=ChatMessage(role=role, content=content),
                    finish_reason=finish_reason,
                )
            ],
            usage=usage,
        )

    def stream_chat(self, request_data: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        raise NotImplementedError("Streaming is deferred to a later week.")

    def generate_embeddings(self, inputs: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embeddings generation is deferred to a later week.")
