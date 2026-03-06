from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.api import ApiServer
from backend.config import load_config
from backend.config.schema import AppConfig
from backend.controller import ControllerService
from backend.logging_system import configure_structured_logging
from backend.runtime import PlaceholderRuntime, RuntimeManager


@dataclass
class BackendApplication:
    config: AppConfig
    runtime_manager: RuntimeManager
    controller: ControllerService
    api_server: ApiServer

    def run(self) -> None:
        try:
            self.api_server.start()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self.api_server.shutdown()
        self.runtime_manager.shutdown()


def bootstrap_application(config_path: str | Path | None = None) -> BackendApplication:
    config = load_config(config_path)
    logger = configure_structured_logging(config.logging)

    logger.info("config_loaded", extra={"event": "startup_step", "step": "config_loaded"})

    runtime_backend = PlaceholderRuntime(config.runtime)
    runtime_manager = RuntimeManager(runtime_backend, logger.getChild("runtime"))
    runtime_manager.startup()

    startup_state = {
        "config_loaded": True,
        "logging_initialized": True,
        "runtime_initialized": True,
        "controller_initialized": True,
        "api_initialized": True,
    }

    controller = ControllerService(
        config=config,
        runtime_manager=runtime_manager,
        logger=logger.getChild("controller"),
        startup_state=startup_state,
    )
    logger.info("controller_initialized", extra={"event": "startup_step", "step": "controller_initialized"})

    api_server = ApiServer(
        host=config.api.host,
        port=config.api.port,
        controller=controller,
        logger=logger.getChild("api"),
    )
    logger.info("api_initialized", extra={"event": "startup_step", "step": "api_initialized"})

    logger.info(
        "startup_complete",
        extra={
            "event": "startup_step",
            "step": "startup_complete",
            "service": config.app.name,
            "version": config.app.version,
        },
    )

    return BackendApplication(
        config=config,
        runtime_manager=runtime_manager,
        controller=controller,
        api_server=api_server,
    )
