from __future__ import annotations

import logging
from dataclasses import asdict

from .interfaces import RuntimeBackend, RuntimeStatus


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
