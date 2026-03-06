from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import (
    ApiConfig,
    AppConfig,
    AppIdentityConfig,
    FeatureFlagsConfig,
    LoggingConfig,
    OperatingModeConfig,
    PlaceholderConfig,
    RuntimeConfig,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "portable-ai-drive-pro.json"
ALLOWED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


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

    default_model = runtime_section.get("default_model")
    if default_model is not None and not isinstance(default_model, str):
        raise ConfigError("Config value 'runtime.default_model' must be a string or null.")

    startup_timeout_seconds = _require_int(runtime_section, "startup_timeout_seconds", "runtime")
    if startup_timeout_seconds <= 0:
        raise ConfigError("Config value 'runtime.startup_timeout_seconds' must be > 0.")

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
            provider=_require_str(runtime_section, "provider", "runtime"),
            default_model=default_model,
            startup_timeout_seconds=startup_timeout_seconds,
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
