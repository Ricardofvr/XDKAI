from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import AppConfig
from backend.runtime.manager import RuntimeManager


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
        runtime_ready = runtime_status.get("state") == "ready"
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
        return {
            "startup_state": self._startup_state,
            "environment": self._config.app.environment,
            "offline_mode": self._config.operating_mode.offline_default,
            "runtime": self._runtime_manager.get_status_payload(),
            "runtime_metadata": self._runtime_manager.get_metadata(),
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

    def dispatch_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Tool dispatch is deferred to Week 3+")

    def validate_policy(self, action: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Policy validation is deferred to Week 3+")
