from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import (
    ApiConfig,
    AppConfig,
    AppIdentityConfig,
    ChatConfig,
    ChatHistoryConfig,
    ChatSessionConfig,
    ChatSystemPromptConfig,
    FeatureFlagsConfig,
    LocalOpenAIProviderConfig,
    LoggingConfig,
    OperatingModeConfig,
    PlaceholderConfig,
    RagChatConfig,
    RagChunkingConfig,
    RagConfig,
    RagIndexConfig,
    RagRetrievalConfig,
    RuntimeConfig,
    RuntimeModelConfig,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "portable-ai-drive-pro.json"
ALLOWED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
ALLOWED_RUNTIME_PROVIDERS = {"placeholder", "local_openai"}
ALLOWED_MODEL_ROLES = {"general", "coder", "embedding"}
GENERATION_MODEL_ROLES = {"general", "coder"}
EMBEDDING_MODEL_ROLE = "embedding"
ALLOWED_RETRIEVAL_METRICS = {"cosine"}


class ConfigError(RuntimeError):
    """Raised when configuration cannot be loaded or validated."""


def _get_section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name)
    if not isinstance(section, dict):
        raise ConfigError(f"Config section '{name}' must be an object.")
    return section


def _require_str(section: dict[str, Any], key: str, section_name: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Config value '{section_name}.{key}' must be a non-empty string.")
    return value


def _require_int(section: dict[str, Any], key: str, section_name: str) -> int:
    value = section.get(key)
    if not isinstance(value, int):
        raise ConfigError(f"Config value '{section_name}.{key}' must be an integer.")
    return value


def _require_bool(section: dict[str, Any], key: str, section_name: str) -> bool:
    value = section.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"Config value '{section_name}.{key}' must be a boolean.")
    return value


def _optional_dict(section: dict[str, Any], key: str, section_name: str) -> dict[str, Any]:
    value = section.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"Config value '{section_name}.{key}' must be an object when provided.")
    return value


def _optional_str(section: dict[str, Any], key: str, section_name: str) -> str | None:
    value = section.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Config value '{section_name}.{key}' must be a non-empty string or null.")
    return value


def _require_list(section: dict[str, Any], key: str, section_name: str) -> list[Any]:
    value = section.get(key)
    if not isinstance(value, list):
        raise ConfigError(f"Config value '{section_name}.{key}' must be an array.")
    return value


def _validate_provider_name(value: str, key: str) -> str:
    if value not in ALLOWED_RUNTIME_PROVIDERS:
        raise ConfigError(
            f"Config value '{key}' must be one of: {', '.join(sorted(ALLOWED_RUNTIME_PROVIDERS))}."
        )
    return value


def _parse_runtime_models(runtime_section: dict[str, Any]) -> list[RuntimeModelConfig]:
    raw_models = _require_list(runtime_section, "models", "runtime")
    if not raw_models:
        raise ConfigError("Config value 'runtime.models' must contain at least one model definition.")

    models: list[RuntimeModelConfig] = []
    seen_names: set[str] = set()

    for index, raw_model in enumerate(raw_models):
        if not isinstance(raw_model, dict):
            raise ConfigError(f"Config value 'runtime.models[{index}]' must be an object.")

        public_name = _require_str(raw_model, "public_name", f"runtime.models[{index}]")
        if public_name in seen_names:
            raise ConfigError(f"Duplicate runtime model public_name '{public_name}'.")
        seen_names.add(public_name)

        role = _require_str(raw_model, "role", f"runtime.models[{index}]")
        if role not in ALLOWED_MODEL_ROLES:
            raise ConfigError(
                f"Config value 'runtime.models[{index}].role' must be one of: {', '.join(sorted(ALLOWED_MODEL_ROLES))}."
            )

        metadata = raw_model.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ConfigError(f"Config value 'runtime.models[{index}].metadata' must be an object.")

        models.append(
            RuntimeModelConfig(
                public_name=public_name,
                provider_model_id=_require_str(raw_model, "provider_model_id", f"runtime.models[{index}]"),
                role=role,
                enabled=_require_bool(raw_model, "enabled", f"runtime.models[{index}]"),
                metadata=metadata,
            )
        )

    if not any(model.enabled for model in models):
        raise ConfigError("At least one runtime model must have enabled=true.")

    return models


def _parse_local_openai_config(runtime_section: dict[str, Any], startup_timeout_seconds: int) -> LocalOpenAIProviderConfig:
    local_openai_section = _optional_dict(runtime_section, "local_openai", "runtime")

    base_url = local_openai_section.get("base_url", "http://127.0.0.1:8081")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ConfigError("Config value 'runtime.local_openai.base_url' must be a non-empty string.")

    timeout_seconds = local_openai_section.get("timeout_seconds", startup_timeout_seconds)
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ConfigError("Config value 'runtime.local_openai.timeout_seconds' must be a positive integer.")

    health_path = local_openai_section.get("health_path", "/health")
    models_path = local_openai_section.get("models_path", "/v1/models")
    chat_completions_path = local_openai_section.get("chat_completions_path", "/v1/chat/completions")
    embeddings_path = local_openai_section.get("embeddings_path", "/v1/embeddings")

    for key, value in (
        ("health_path", health_path),
        ("models_path", models_path),
        ("chat_completions_path", chat_completions_path),
        ("embeddings_path", embeddings_path),
    ):
        if not isinstance(value, str) or not value.startswith("/"):
            raise ConfigError(f"Config value 'runtime.local_openai.{key}' must be an absolute path string.")

    return LocalOpenAIProviderConfig(
        base_url=base_url.rstrip("/"),
        timeout_seconds=timeout_seconds,
        health_path=health_path,
        models_path=models_path,
        chat_completions_path=chat_completions_path,
        embeddings_path=embeddings_path,
    )


def _parse_rag_config(
    data: dict[str, Any],
    enabled_embedding_names: set[str],
    runtime_default_embedding_model: str | None,
) -> RagConfig:
    rag_section_raw = data.get("rag", {})
    if not isinstance(rag_section_raw, dict):
        raise ConfigError("Config section 'rag' must be an object when provided.")

    rag_enabled = rag_section_raw.get("enabled", True)
    if not isinstance(rag_enabled, bool):
        raise ConfigError("Config value 'rag.enabled' must be a boolean.")

    rag_default_embedding_model = rag_section_raw.get("default_embedding_model", runtime_default_embedding_model)
    if rag_default_embedding_model is not None and (
        not isinstance(rag_default_embedding_model, str) or not rag_default_embedding_model.strip()
    ):
        raise ConfigError("Config value 'rag.default_embedding_model' must be a non-empty string or null.")

    if rag_enabled and not rag_default_embedding_model:
        raise ConfigError(
            "Config value 'rag.default_embedding_model' must be set when rag.enabled=true, "
            "or runtime.default_embedding_model must be configured."
        )

    if rag_default_embedding_model and rag_default_embedding_model not in enabled_embedding_names:
        raise ConfigError(
            "Config value 'rag.default_embedding_model' must match an enabled runtime model with role embedding."
        )

    chunking_section = rag_section_raw.get("chunking", {})
    if not isinstance(chunking_section, dict):
        raise ConfigError("Config value 'rag.chunking' must be an object when provided.")

    chunk_size = chunking_section.get("chunk_size", 1000)
    chunk_overlap = chunking_section.get("chunk_overlap", 200)
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ConfigError("Config value 'rag.chunking.chunk_size' must be a positive integer.")
    if not isinstance(chunk_overlap, int) or chunk_overlap < 0:
        raise ConfigError("Config value 'rag.chunking.chunk_overlap' must be an integer >= 0.")
    if chunk_overlap >= chunk_size:
        raise ConfigError("Config value 'rag.chunking.chunk_overlap' must be smaller than chunk_size.")

    index_section = rag_section_raw.get("index", {})
    if not isinstance(index_section, dict):
        raise ConfigError("Config value 'rag.index' must be an object when provided.")

    index_directory = index_section.get("directory", "data/index")
    if not isinstance(index_directory, str) or not index_directory.strip():
        raise ConfigError("Config value 'rag.index.directory' must be a non-empty string.")

    resolved_index_dir = Path(index_directory)
    if not resolved_index_dir.is_absolute():
        resolved_index_dir = (PROJECT_ROOT / resolved_index_dir).resolve()

    vectors_db_filename = index_section.get("vectors_db_filename", "vectors.db")
    documents_filename = index_section.get("documents_filename", "documents.json")
    metadata_filename = index_section.get("metadata_filename", "metadata.json")
    for key, value in (
        ("vectors_db_filename", vectors_db_filename),
        ("documents_filename", documents_filename),
        ("metadata_filename", metadata_filename),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"Config value 'rag.index.{key}' must be a non-empty string.")
        if "/" in value or "\\" in value:
            raise ConfigError(f"Config value 'rag.index.{key}' must be a filename, not a path.")

    retrieval_config = _parse_rag_retrieval_config(rag_section_raw)
    chat_config = _parse_rag_chat_config(rag_section_raw, default_min_similarity=retrieval_config.min_similarity)

    return RagConfig(
        enabled=rag_enabled,
        default_embedding_model=rag_default_embedding_model,
        chunking=RagChunkingConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
        index=RagIndexConfig(
            directory=str(resolved_index_dir),
            vectors_db_filename=vectors_db_filename,
            documents_filename=documents_filename,
            metadata_filename=metadata_filename,
        ),
        retrieval=retrieval_config,
        chat=chat_config,
    )


def _parse_chat_config(data: dict[str, Any]) -> ChatConfig:
    chat_section_raw = data.get("chat", {})
    if not isinstance(chat_section_raw, dict):
        raise ConfigError("Config section 'chat' must be an object when provided.")

    include_session_metadata = chat_section_raw.get("include_session_metadata", True)
    if not isinstance(include_session_metadata, bool):
        raise ConfigError("Config value 'chat.include_session_metadata' must be a boolean.")

    debug_session = chat_section_raw.get("debug_session", False)
    if not isinstance(debug_session, bool):
        raise ConfigError("Config value 'chat.debug_session' must be a boolean.")

    session_section = chat_section_raw.get("session", {})
    if not isinstance(session_section, dict):
        raise ConfigError("Config value 'chat.session' must be an object when provided.")

    session_directory = session_section.get("directory", "data/sessions")
    if not isinstance(session_directory, str) or not session_directory.strip():
        raise ConfigError("Config value 'chat.session.directory' must be a non-empty string.")
    resolved_session_dir = Path(session_directory)
    if not resolved_session_dir.is_absolute():
        resolved_session_dir = (PROJECT_ROOT / resolved_session_dir).resolve()

    persist_to_disk = session_section.get("persist_to_disk", True)
    if not isinstance(persist_to_disk, bool):
        raise ConfigError("Config value 'chat.session.persist_to_disk' must be a boolean.")

    history_section = chat_section_raw.get("history", {})
    if not isinstance(history_section, dict):
        raise ConfigError("Config value 'chat.history' must be an object when provided.")

    max_turns = history_section.get("max_turns", 8)
    if not isinstance(max_turns, int) or max_turns <= 0:
        raise ConfigError("Config value 'chat.history.max_turns' must be a positive integer.")

    max_characters = history_section.get("max_characters", 7000)
    if not isinstance(max_characters, int) or max_characters <= 0:
        raise ConfigError("Config value 'chat.history.max_characters' must be a positive integer.")

    retain_system_prompt = history_section.get("retain_system_prompt", True)
    if not isinstance(retain_system_prompt, bool):
        raise ConfigError("Config value 'chat.history.retain_system_prompt' must be a boolean.")

    system_prompt_section = chat_section_raw.get("system_prompt", {})
    if not isinstance(system_prompt_section, dict):
        raise ConfigError("Config value 'chat.system_prompt' must be an object when provided.")

    system_prompt_text = system_prompt_section.get(
        "text",
        (
            "You are Portable AI Drive PRO, a private local assistant. "
            "Be concise, accurate, and explicit about uncertainty."
        ),
    )
    if not isinstance(system_prompt_text, str):
        raise ConfigError("Config value 'chat.system_prompt.text' must be a string.")

    return ChatConfig(
        include_session_metadata=include_session_metadata,
        debug_session=debug_session,
        session=ChatSessionConfig(
            directory=str(resolved_session_dir),
            persist_to_disk=persist_to_disk,
        ),
        history=ChatHistoryConfig(
            max_turns=max_turns,
            max_characters=max_characters,
            retain_system_prompt=retain_system_prompt,
        ),
        system_prompt=ChatSystemPromptConfig(text=system_prompt_text.strip()),
    )


def _parse_rag_retrieval_config(rag_section_raw: dict[str, Any]) -> RagRetrievalConfig:
    retrieval_section = rag_section_raw.get("retrieval", {})
    if not isinstance(retrieval_section, dict):
        raise ConfigError("Config value 'rag.retrieval' must be an object when provided.")

    top_k = retrieval_section.get("top_k", 3)
    if not isinstance(top_k, int) or top_k <= 0:
        raise ConfigError("Config value 'rag.retrieval.top_k' must be a positive integer.")

    similarity_metric = retrieval_section.get("similarity_metric", "cosine")
    if not isinstance(similarity_metric, str) or not similarity_metric.strip():
        raise ConfigError("Config value 'rag.retrieval.similarity_metric' must be a non-empty string.")
    if similarity_metric not in ALLOWED_RETRIEVAL_METRICS:
        raise ConfigError(
            f"Config value 'rag.retrieval.similarity_metric' must be one of: {', '.join(sorted(ALLOWED_RETRIEVAL_METRICS))}."
        )

    min_similarity_raw = retrieval_section.get("min_similarity", 0.0)
    if not isinstance(min_similarity_raw, (int, float)):
        raise ConfigError("Config value 'rag.retrieval.min_similarity' must be a number.")
    min_similarity = float(min_similarity_raw)
    if min_similarity < -1.0 or min_similarity > 1.0:
        raise ConfigError("Config value 'rag.retrieval.min_similarity' must be between -1.0 and 1.0.")

    return RagRetrievalConfig(
        top_k=top_k,
        similarity_metric=similarity_metric,
        min_similarity=min_similarity,
    )


def _parse_rag_chat_config(rag_section_raw: dict[str, Any], default_min_similarity: float) -> RagChatConfig:
    chat_section = rag_section_raw.get("chat", {})
    if not isinstance(chat_section, dict):
        raise ConfigError("Config value 'rag.chat' must be an object when provided.")

    enabled = chat_section.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError("Config value 'rag.chat.enabled' must be a boolean.")

    max_context_chunks = chat_section.get("max_context_chunks", 3)
    if not isinstance(max_context_chunks, int) or max_context_chunks <= 0:
        raise ConfigError("Config value 'rag.chat.max_context_chunks' must be a positive integer.")

    retrieval_fetch_k = chat_section.get("retrieval_fetch_k", max(max_context_chunks * 4, max_context_chunks))
    if not isinstance(retrieval_fetch_k, int) or retrieval_fetch_k <= 0:
        raise ConfigError("Config value 'rag.chat.retrieval_fetch_k' must be a positive integer.")
    if retrieval_fetch_k < max_context_chunks:
        raise ConfigError("Config value 'rag.chat.retrieval_fetch_k' must be >= rag.chat.max_context_chunks.")

    max_context_characters = chat_section.get("max_context_characters", 5000)
    if not isinstance(max_context_characters, int) or max_context_characters <= 0:
        raise ConfigError("Config value 'rag.chat.max_context_characters' must be a positive integer.")

    max_chunks_per_document = chat_section.get("max_chunks_per_document", 2)
    if not isinstance(max_chunks_per_document, int) or max_chunks_per_document <= 0:
        raise ConfigError("Config value 'rag.chat.max_chunks_per_document' must be a positive integer.")

    deduplicate_results = chat_section.get("deduplicate_results", True)
    if not isinstance(deduplicate_results, bool):
        raise ConfigError("Config value 'rag.chat.deduplicate_results' must be a boolean.")

    near_duplicate_threshold_raw = chat_section.get("near_duplicate_threshold", 0.92)
    if not isinstance(near_duplicate_threshold_raw, (int, float)):
        raise ConfigError("Config value 'rag.chat.near_duplicate_threshold' must be a number.")
    near_duplicate_threshold = float(near_duplicate_threshold_raw)
    if near_duplicate_threshold < 0.0 or near_duplicate_threshold > 1.0:
        raise ConfigError("Config value 'rag.chat.near_duplicate_threshold' must be between 0.0 and 1.0.")

    min_similarity_raw = chat_section.get("min_similarity", default_min_similarity)
    if not isinstance(min_similarity_raw, (int, float)):
        raise ConfigError("Config value 'rag.chat.min_similarity' must be a number.")
    min_similarity = float(min_similarity_raw)
    if min_similarity < -1.0 or min_similarity > 1.0:
        raise ConfigError("Config value 'rag.chat.min_similarity' must be between -1.0 and 1.0.")

    context_prefix = chat_section.get(
        "context_prefix",
        "You have access to the following local context. Use it when relevant to answer the user question.",
    )
    if not isinstance(context_prefix, str) or not context_prefix.strip():
        raise ConfigError("Config value 'rag.chat.context_prefix' must be a non-empty string.")

    include_source_metadata = chat_section.get("include_source_metadata", True)
    if not isinstance(include_source_metadata, bool):
        raise ConfigError("Config value 'rag.chat.include_source_metadata' must be a boolean.")

    debug_retrieval = chat_section.get("debug_retrieval", False)
    if not isinstance(debug_retrieval, bool):
        raise ConfigError("Config value 'rag.chat.debug_retrieval' must be a boolean.")

    return RagChatConfig(
        enabled=enabled,
        retrieval_fetch_k=retrieval_fetch_k,
        max_context_chunks=max_context_chunks,
        max_context_characters=max_context_characters,
        max_chunks_per_document=max_chunks_per_document,
        deduplicate_results=deduplicate_results,
        near_duplicate_threshold=near_duplicate_threshold,
        min_similarity=min_similarity,
        context_prefix=context_prefix.strip(),
        include_source_metadata=include_source_metadata,
        debug_retrieval=debug_retrieval,
    )


def load_config(config_path: str | Path | None = None) -> AppConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file '{path}': {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Root config must be a JSON object.")

    app_section = _get_section(data, "app")
    api_section = _get_section(data, "api")
    logging_section = _get_section(data, "logging")
    runtime_section = _get_section(data, "runtime")
    operating_mode_section = _get_section(data, "operating_mode")
    feature_flags_section = _get_section(data, "feature_flags")
    placeholders_section = _get_section(data, "placeholders")

    api_port = _require_int(api_section, "port", "api")
    if api_port < 1 or api_port > 65535:
        raise ConfigError("Config value 'api.port' must be between 1 and 65535.")

    log_level = _require_str(logging_section, "level", "logging").upper()
    if log_level not in ALLOWED_LOG_LEVELS:
        raise ConfigError(
            f"Config value 'logging.level' must be one of: {', '.join(sorted(ALLOWED_LOG_LEVELS))}."
        )

    log_directory = _require_str(logging_section, "directory", "logging")
    log_filename = _require_str(logging_section, "filename", "logging")
    resolved_log_dir = Path(log_directory)
    if not resolved_log_dir.is_absolute():
        resolved_log_dir = (PROJECT_ROOT / resolved_log_dir).resolve()

    startup_timeout_seconds = _require_int(runtime_section, "startup_timeout_seconds", "runtime")
    if startup_timeout_seconds <= 0:
        raise ConfigError("Config value 'runtime.startup_timeout_seconds' must be > 0.")

    provider = _validate_provider_name(_require_str(runtime_section, "provider", "runtime"), "runtime.provider")

    fallback_provider = _optional_str(runtime_section, "fallback_provider", "runtime")
    if fallback_provider is not None:
        fallback_provider = _validate_provider_name(fallback_provider, "runtime.fallback_provider")

    allow_fallback_to_placeholder = runtime_section.get("allow_fallback_to_placeholder", False)
    if not isinstance(allow_fallback_to_placeholder, bool):
        raise ConfigError("Config value 'runtime.allow_fallback_to_placeholder' must be a boolean.")

    default_model = runtime_section.get("default_model")
    if default_model is not None and not isinstance(default_model, str):
        raise ConfigError("Config value 'runtime.default_model' must be a string or null.")

    default_embedding_model = runtime_section.get("default_embedding_model")
    if default_embedding_model is not None and not isinstance(default_embedding_model, str):
        raise ConfigError("Config value 'runtime.default_embedding_model' must be a string or null.")

    runtime_models = _parse_runtime_models(runtime_section)

    enabled_generation_names = {
        model.public_name for model in runtime_models if model.enabled and model.role in GENERATION_MODEL_ROLES
    }
    enabled_embedding_names = {
        model.public_name for model in runtime_models if model.enabled and model.role == EMBEDDING_MODEL_ROLE
    }

    if default_model is not None and default_model not in enabled_generation_names:
        raise ConfigError(
            "Config value 'runtime.default_model' must match an enabled runtime model with role general/coder."
        )

    if default_embedding_model is not None and default_embedding_model not in enabled_embedding_names:
        raise ConfigError(
            "Config value 'runtime.default_embedding_model' must match an enabled runtime model with role embedding."
        )

    local_openai = _parse_local_openai_config(runtime_section, startup_timeout_seconds)
    rag_config = _parse_rag_config(
        data=data,
        enabled_embedding_names=enabled_embedding_names,
        runtime_default_embedding_model=default_embedding_model,
    )
    chat_config = _parse_chat_config(data)

    app_config = AppConfig(
        app=AppIdentityConfig(
            name=_require_str(app_section, "name", "app"),
            version=_require_str(app_section, "version", "app"),
            environment=_require_str(app_section, "environment", "app"),
        ),
        api=ApiConfig(
            host=_require_str(api_section, "host", "api"),
            port=api_port,
        ),
        logging=LoggingConfig(
            level=log_level,
            directory=str(resolved_log_dir),
            filename=log_filename,
            to_stdout=_require_bool(logging_section, "to_stdout", "logging"),
        ),
        runtime=RuntimeConfig(
            provider=provider,
            fallback_provider=fallback_provider,
            allow_fallback_to_placeholder=allow_fallback_to_placeholder,
            default_model=default_model,
            default_embedding_model=default_embedding_model,
            startup_timeout_seconds=startup_timeout_seconds,
            models=runtime_models,
            local_openai=local_openai,
        ),
        operating_mode=OperatingModeConfig(
            offline_default=_require_bool(operating_mode_section, "offline_default", "operating_mode")
        ),
        feature_flags=FeatureFlagsConfig(
            openai_compatible_api=_require_bool(
                feature_flags_section, "openai_compatible_api", "feature_flags"
            ),
            tool_execution=_require_bool(feature_flags_section, "tool_execution", "feature_flags"),
            memory=_require_bool(feature_flags_section, "memory", "feature_flags"),
            research=_require_bool(feature_flags_section, "research", "feature_flags"),
        ),
        chat=chat_config,
        rag=rag_config,
        placeholders=PlaceholderConfig(
            policy_rules=_optional_dict(placeholders_section, "policy_rules", "placeholders"),
            tool_permissions=_optional_dict(placeholders_section, "tool_permissions", "placeholders"),
            memory_settings=_optional_dict(placeholders_section, "memory_settings", "placeholders"),
            research_settings=_optional_dict(placeholders_section, "research_settings", "placeholders"),
        ),
        raw=data,
    )

    return app_config
