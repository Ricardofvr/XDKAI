from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import AppConfig
from backend.runtime.interfaces import ChatGenerationRequest, RuntimeInvocationError, RuntimeUnavailableError
from backend.runtime.manager import RuntimeManager

from .errors import ControllerRequestError


class ControllerService:
    """Central orchestration boundary for API-facing requests."""

    def __init__(
        self,
        config: AppConfig,
        runtime_manager: RuntimeManager,
        logger: logging.Logger,
        startup_state: dict[str, bool],
    ) -> None:
        self._config = config
        self._runtime_manager = runtime_manager
        self._logger = logger
        self._startup_state = startup_state

        # Week 2 placeholders for future orchestrated subsystems.
        self._policy_manager = None
        self._tool_dispatcher = None
        self._memory_manager = None
        self._research_manager = None

    def get_health(self) -> dict[str, Any]:
        runtime_status = self._runtime_manager.get_status_payload()
        runtime_ready = bool(runtime_status.get("ready"))
        status = "ok" if runtime_ready else "degraded"

        return {
            "status": status,
            "service": self._config.app.name,
            "subsystems": {
                "controller": "ready",
                "runtime": runtime_status.get("state"),
                "config": "loaded",
            },
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def get_version_info(self) -> dict[str, Any]:
        return {
            "name": self._config.app.name,
            "version": self._config.app.version,
            "environment": self._config.app.environment,
        }

    def get_system_status(self) -> dict[str, Any]:
        runtime_status = self._runtime_manager.get_status_payload()
        return {
            "startup_state": self._startup_state,
            "environment": self._config.app.environment,
            "offline_mode": self._config.operating_mode.offline_default,
            "runtime": runtime_status,
            "runtime_metadata": self._runtime_manager.get_metadata(),
            "model_registry": self._runtime_manager.get_model_registry_payload(),
            "feature_flags": {
                "openai_compatible_api": self._config.feature_flags.openai_compatible_api,
                "tool_execution": self._config.feature_flags.tool_execution,
                "memory": self._config.feature_flags.memory,
                "research": self._config.feature_flags.research,
            },
            "future_modules": {
                "policy_validation": "deferred",
                "tool_dispatch": "deferred",
                "memory_manager": "deferred",
                "research_manager": "deferred",
            },
        }

    def list_models(self) -> dict[str, Any]:
        self._logger.info("controller_list_models", extra={"event": "controller_route", "route": "list_models"})
        models = self._runtime_manager.list_models()
        return {
            "object": "list",
            "data": [
                {
                    "id": model.id,
                    "object": model.object,
                    "created": model.created,
                    "owned_by": model.owned_by,
                }
                for model in models
            ],
        }

    def create_chat_completion(self, request: ChatGenerationRequest) -> dict[str, Any]:
        self._logger.info(
            "controller_chat_completion_received",
            extra={
                "event": "controller_route",
                "route": "chat_completions",
                "model": request.model,
                "stream": request.stream,
                "request_id": request.request_id,
            },
        )

        if request.stream:
            raise ControllerRequestError(
                "stream=true is not implemented yet.",
                error_type="unsupported_feature",
                status_code=400,
            )

        available_models = {model.id for model in self._runtime_manager.list_models()}
        if request.model not in available_models:
            raise ControllerRequestError(
                f"Model '{request.model}' is not available.",
                error_type="model_not_found",
                status_code=404,
            )

        try:
            runtime_response = self._runtime_manager.generate_chat(request)
        except RuntimeUnavailableError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_unavailable",
                status_code=503,
            ) from exc
        except RuntimeInvocationError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_invocation_error",
                status_code=502,
            ) from exc

        if not runtime_response.choices:
            raise ControllerRequestError(
                "Runtime returned no choices.",
                error_type="runtime_error",
                status_code=500,
            )

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created_ts = int(time.time())

        response = {
            "id": completion_id,
            "object": "chat.completion",
            "created": created_ts,
            "model": runtime_response.model,
            "choices": [
                {
                    "index": choice.index,
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content,
                    },
                    "finish_reason": choice.finish_reason,
                }
                for choice in runtime_response.choices
            ],
            "usage": runtime_response.usage,
        }

        self._logger.info(
            "controller_chat_completion_ready",
            extra={
                "event": "controller_route",
                "route": "chat_completions",
                "request_id": request.request_id,
                "completion_id": completion_id,
            },
        )

        return response

    def dispatch_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Tool dispatch is deferred to Week 4+")

    def validate_policy(self, action: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Policy validation is deferred to Week 4+")
