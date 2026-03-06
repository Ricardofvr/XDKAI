from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from backend.api import ApiServer
from backend.config import load_config
from backend.config.schema import AppConfig
from backend.conversation import ConversationSessionManager
from backend.controller import ControllerService
from backend.logging_system import configure_structured_logging
from backend.rag.vector_store import SQLiteVectorStore
from backend.runtime import RuntimeManager, build_runtime_backends


@dataclass
class BackendCore:
    config: AppConfig
    runtime_manager: RuntimeManager
    controller: ControllerService
    vector_store: SQLiteVectorStore
    logger: logging.Logger

    def shutdown(self) -> None:
        self.runtime_manager.shutdown()


@dataclass
class BackendApplication:
    config: AppConfig
    runtime_manager: RuntimeManager
    controller: ControllerService
    vector_store: SQLiteVectorStore
    api_server: ApiServer

    def run(self) -> None:
        try:
            self.api_server.start()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self.api_server.shutdown()
        self.runtime_manager.shutdown()


def bootstrap_core(config_path: str | Path | None = None) -> BackendCore:
    config = load_config(config_path)
    logger = configure_structured_logging(config.logging)

    logger.info("config_loaded", extra={"event": "startup_step", "step": "config_loaded"})

    primary_backend, fallback_backend = build_runtime_backends(config.runtime, logger.getChild("runtime.providers"))
    runtime_manager = RuntimeManager(
        primary_backend=primary_backend,
        fallback_backend=fallback_backend,
        selected_provider=config.runtime.provider,
        fallback_provider=config.runtime.fallback_provider,
        logger=logger.getChild("runtime"),
    )
    runtime_manager.startup()

    vector_store = SQLiteVectorStore(
        index_directory=config.rag.index.directory,
        vectors_db_filename=config.rag.index.vectors_db_filename,
        documents_filename=config.rag.index.documents_filename,
        metadata_filename=config.rag.index.metadata_filename,
    )
    vector_store.initialize()
    logger.info(
        "rag_index_initialized",
        extra={
            "event": "startup_step",
            "step": "rag_index_initialized",
            "index_location": config.rag.index.directory,
            "vectors_db": config.rag.index.vectors_db_filename,
        },
    )

    startup_state = {
        "config_loaded": True,
        "logging_initialized": True,
        "runtime_initialized": True,
        "rag_index_initialized": True,
        "conversation_initialized": True,
        "controller_initialized": True,
        "api_initialized": False,
    }

    session_manager = ConversationSessionManager(
        directory=config.chat.session.directory,
        persist_to_disk=config.chat.session.persist_to_disk,
        logger=logger.getChild("conversation.sessions"),
    )
    logger.info(
        "conversation_initialized",
        extra={
            "event": "startup_step",
            "step": "conversation_initialized",
            "directory": config.chat.session.directory,
            "persist_to_disk": config.chat.session.persist_to_disk,
        },
    )

    controller = ControllerService(
        config=config,
        runtime_manager=runtime_manager,
        logger=logger.getChild("controller"),
        startup_state=startup_state,
        rag_vector_store=vector_store,
        session_manager=session_manager,
    )
    logger.info("controller_initialized", extra={"event": "startup_step", "step": "controller_initialized"})

    return BackendCore(
        config=config,
        runtime_manager=runtime_manager,
        controller=controller,
        vector_store=vector_store,
        logger=logger,
    )


def bootstrap_application(config_path: str | Path | None = None) -> BackendApplication:
    core = bootstrap_core(config_path=config_path)
    logger = core.logger

    api_server = ApiServer(
        host=core.config.api.host,
        port=core.config.api.port,
        controller=core.controller,
        logger=logger.getChild("api"),
    )
    core.controller.mark_startup_step("api_initialized")
    logger.info("api_initialized", extra={"event": "startup_step", "step": "api_initialized"})

    logger.info(
        "startup_complete",
        extra={
            "event": "startup_step",
            "step": "startup_complete",
            "service": core.config.app.name,
            "version": core.config.app.version,
        },
    )

    return BackendApplication(
        config=core.config,
        runtime_manager=core.runtime_manager,
        controller=core.controller,
        vector_store=core.vector_store,
        api_server=api_server,
    )
