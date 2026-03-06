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
    EmbeddingGenerationRequest,
    EmbeddingGenerationResponse,
    EmbeddingVector,
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
        self._embedding_ready = False
        self._startup_error: str | None = None
        self._provider_models: set[str] = set()

        self._last_chat_error: str | None = None
        self._last_chat_latency_ms: int | None = None
        self._last_embedding_error: str | None = None
        self._last_embedding_latency_ms: int | None = None

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

    def _enabled_generation_models(self) -> list[ModelInfo]:
        return [model for model in self._enabled_models() if model.role in {"general", "coder"}]

    def _enabled_embedding_models(self) -> list[ModelInfo]:
        return [model for model in self._enabled_models() if model.role == "embedding"]

    def _active_model(self) -> str | None:
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
            self._provider_reachable = False
            raise RuntimeUnavailableError(
                f"Local runtime request timed out after {self._provider_cfg.timeout_seconds}s: {url}"
            ) from exc
        except error.URLError as exc:
            self._provider_reachable = False
            reason = getattr(exc, "reason", str(exc))
            raise RuntimeUnavailableError(f"Unable to reach local runtime at {url}: {reason}") from exc
        except OSError as exc:
            self._provider_reachable = False
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
            self._provider_reachable = False
            raise RuntimeUnavailableError(
                f"Local runtime request timed out after {self._provider_cfg.timeout_seconds}s: {url}"
            ) from exc
        except error.URLError as exc:
            self._provider_reachable = False
            reason = getattr(exc, "reason", str(exc))
            raise RuntimeUnavailableError(f"Unable to reach local runtime at {url}: {reason}") from exc
        except OSError as exc:
            self._provider_reachable = False
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

    def _provider_has_model(self, provider_model_id: str | None) -> bool:
        return bool(provider_model_id) and provider_model_id in self._provider_models

    def _evaluate_capability(self) -> tuple[bool, bool, str]:
        enabled_generation = self._enabled_generation_models()
        enabled_embedding = self._enabled_embedding_models()

        generation_ready = any(self._provider_has_model(model.provider_model_id) for model in enabled_generation)
        embedding_ready = any(self._provider_has_model(model.provider_model_id) for model in enabled_embedding)

        if generation_ready or embedding_ready:
            return generation_ready, embedding_ready, "Runtime capabilities detected from provider model list."

        if not self._provider_models:
            return False, False, "Provider returned no models."

        return False, False, "No enabled registry model is available in provider model list."

    def startup(self) -> None:
        self._started = True
        self._provider_reachable = False
        self._generation_ready = False
        self._embedding_ready = False
        self._startup_error = None

        try:
            self._probe_health()
            self._provider_reachable = True
            self._refresh_provider_models()

            generation_ready, embedding_ready, reason = self._evaluate_capability()
            self._generation_ready = generation_ready
            self._embedding_ready = embedding_ready

            if not (self._generation_ready or self._embedding_ready):
                self._startup_error = reason
                self._logger.warning(
                    "local_openai_runtime_degraded",
                    extra={
                        "event": "runtime_provider",
                        "provider": "local_openai",
                        "base_url": self._provider_cfg.base_url,
                        "reason": reason,
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
                        "generation_ready": self._generation_ready,
                        "embedding_ready": self._embedding_ready,
                        "detected_provider_models": sorted(self._provider_models),
                    },
                )
        except (RuntimeUnavailableError, RuntimeInvocationError) as exc:
            self._startup_error = str(exc)
            self._provider_reachable = False
            self._generation_ready = False
            self._embedding_ready = False
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
        self._embedding_ready = False

    def get_status(self) -> RuntimeStatus:
        ready = self._generation_ready or self._embedding_ready
        if not self._started:
            state = "stopped"
        elif ready:
            state = "ready"
        else:
            state = "degraded"

        enabled_models = self._enabled_models()

        return RuntimeStatus(
            state=state,
            provider="local_openai",
            mode="provider",
            initialized=self._started,
            ready=ready,
            generation_ready=self._generation_ready,
            embedding_ready=self._embedding_ready,
            provider_reachable=self._provider_reachable,
            active_model=self._active_model() or self._active_embedding_model(),
            models_available=[model.id for model in enabled_models],
            details={
                "base_url": self._provider_cfg.base_url,
                "provider_health_path": self._provider_cfg.health_path,
                "provider_models_path": self._provider_cfg.models_path,
                "provider_embeddings_path": self._provider_cfg.embeddings_path,
                "detected_provider_models": sorted(self._provider_models),
                "configured_enabled_generation_models": [model.id for model in self._enabled_generation_models()],
                "configured_enabled_embedding_models": [model.id for model in self._enabled_embedding_models()],
                "generation_capable": self._generation_ready,
                "embedding_capable": self._embedding_ready,
                "startup_error": self._startup_error,
                "last_chat_error": self._last_chat_error,
                "last_chat_latency_ms": self._last_chat_latency_ms,
                "last_embedding_error": self._last_embedding_error,
                "last_embedding_latency_ms": self._last_embedding_latency_ms,
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
                "embedding_ready": self._embedding_ready,
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
            "supports_embeddings": True,
            "supports_streaming": False,
            "mode": "provider",
            "base_url": self._provider_cfg.base_url,
            "generation_ready": self._generation_ready,
            "embedding_ready": self._embedding_ready,
        }

    def _resolve_registry_model(self, requested_model: str, *, role: str) -> ModelInfo:
        enabled = self._enabled_models()
        for model in enabled:
            if model.id != requested_model:
                continue
            if role == "chat" and model.role not in {"general", "coder"}:
                raise RuntimeInvocationError(
                    f"Model '{requested_model}' is not configured for chat generation (role={model.role})."
                )
            if role == "embedding" and model.role != "embedding":
                raise RuntimeInvocationError(
                    f"Model '{requested_model}' is not configured for embeddings (role={model.role})."
                )
            if not model.provider_model_id:
                raise RuntimeInvocationError(f"Model '{requested_model}' has no provider model mapping.")
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
        if not self._generation_ready:
            raise RuntimeUnavailableError("Local runtime provider is not generation-ready.")

        registry_model = self._resolve_registry_model(request_data.model, role="chat")

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

    def generate_embeddings(self, request_data: EmbeddingGenerationRequest) -> EmbeddingGenerationResponse:
        if not self._started or not self._provider_reachable:
            raise RuntimeUnavailableError("Local runtime provider is unreachable.")
        if not self._embedding_ready:
            raise RuntimeUnavailableError("Local runtime provider is not embedding-ready.")

        registry_model = self._resolve_registry_model(request_data.model, role="embedding")

        try:
            self._ensure_provider_model_available(registry_model)

            provider_input: str | list[str]
            if len(request_data.input_texts) == 1:
                provider_input = request_data.input_texts[0]
            else:
                provider_input = request_data.input_texts

            payload: dict[str, Any] = {
                "model": registry_model.provider_model_id,
                "input": provider_input,
            }
            if request_data.encoding_format is not None:
                payload["encoding_format"] = request_data.encoding_format
            if request_data.user is not None:
                payload["user"] = request_data.user

            started = time.monotonic()
            response_payload = self._request_json("POST", self._provider_cfg.embeddings_path, payload=payload)
            latency_ms = int((time.monotonic() - started) * 1000)

            data_raw = response_payload.get("data")
            if not isinstance(data_raw, list) or not data_raw:
                raise RuntimeInvocationError("Local runtime embeddings response missing non-empty 'data' array.")

            vectors: list[EmbeddingVector] = []
            for idx, item in enumerate(data_raw):
                if not isinstance(item, dict):
                    raise RuntimeInvocationError("Local runtime embeddings entry must be an object.")

                embedding_raw = item.get("embedding")
                if not isinstance(embedding_raw, list) or not embedding_raw:
                    raise RuntimeInvocationError("Local runtime embeddings entry missing non-empty 'embedding' list.")

                embedding: list[float] = []
                for value in embedding_raw:
                    if isinstance(value, (int, float)):
                        embedding.append(float(value))
                    else:
                        raise RuntimeInvocationError("Local runtime embedding vector contains non-numeric value.")

                index = item.get("index", idx)
                if not isinstance(index, int):
                    index = idx

                vectors.append(EmbeddingVector(index=index, embedding=embedding))

            usage_raw = response_payload.get("usage", {})
            usage = {
                "prompt_tokens": self._coerce_non_negative_int(usage_raw.get("prompt_tokens", 0))
                if isinstance(usage_raw, dict)
                else 0,
                "total_tokens": self._coerce_non_negative_int(usage_raw.get("total_tokens", 0))
                if isinstance(usage_raw, dict)
                else 0,
            }

            self._last_embedding_error = None
            self._last_embedding_latency_ms = latency_ms

            self._logger.info(
                "local_openai_embeddings_completed",
                extra={
                    "event": "runtime_provider",
                    "provider": "local_openai",
                    "public_model": request_data.model,
                    "provider_model_id": registry_model.provider_model_id,
                    "input_count": len(request_data.input_texts),
                    "latency_ms": latency_ms,
                    "request_id": request_data.request_id,
                },
            )

            return EmbeddingGenerationResponse(
                model=request_data.model,
                data=vectors,
                usage=usage,
            )
        except (RuntimeInvocationError, RuntimeUnavailableError) as exc:
            self._last_embedding_error = str(exc)
            raise

    def stream_chat(self, request_data: ChatGenerationRequest) -> Iterator[ChatGenerationChoice]:
        raise NotImplementedError("Streaming is deferred to a later week.")
