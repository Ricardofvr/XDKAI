from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import (
    ApiConfig,
    AppConfig,
    AppIdentityConfig,
    FeatureFlagsConfig,
    LocalOpenAIProviderConfig,
    LoggingConfig,
    OperatingModeConfig,
    PlaceholderConfig,
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
        placeholders=PlaceholderConfig(
            policy_rules=_optional_dict(placeholders_section, "policy_rules", "placeholders"),
            tool_permissions=_optional_dict(placeholders_section, "tool_permissions", "placeholders"),
            memory_settings=_optional_dict(placeholders_section, "memory_settings", "placeholders"),
            research_settings=_optional_dict(placeholders_section, "research_settings", "placeholders"),
        ),
        raw=data,
    )

    return app_config
