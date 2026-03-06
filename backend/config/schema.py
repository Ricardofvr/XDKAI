from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AppIdentityConfig:
    name: str
    version: str
    environment: str


@dataclass(frozen=True)
class ApiConfig:
    host: str
    port: int


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    directory: str
    filename: str
    to_stdout: bool = True


@dataclass(frozen=True)
class RuntimeConfig:
    provider: str
    default_model: str | None
    startup_timeout_seconds: int


@dataclass(frozen=True)
class OperatingModeConfig:
    offline_default: bool


@dataclass(frozen=True)
class FeatureFlagsConfig:
    openai_compatible_api: bool
    tool_execution: bool
    memory: bool
    research: bool


@dataclass(frozen=True)
class PlaceholderConfig:
    policy_rules: dict[str, Any] = field(default_factory=dict)
    tool_permissions: dict[str, Any] = field(default_factory=dict)
    memory_settings: dict[str, Any] = field(default_factory=dict)
    research_settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    app: AppIdentityConfig
    api: ApiConfig
    logging: LoggingConfig
    runtime: RuntimeConfig
    operating_mode: OperatingModeConfig
    feature_flags: FeatureFlagsConfig
    placeholders: PlaceholderConfig
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
