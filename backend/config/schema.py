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
class RuntimeModelConfig:
    public_name: str
    provider_model_id: str
    role: str
    enabled: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalOpenAIProviderConfig:
    base_url: str
    timeout_seconds: int
    health_path: str
    models_path: str
    chat_completions_path: str
    embeddings_path: str


@dataclass(frozen=True)
class RuntimeConfig:
    provider: str
    fallback_provider: str | None
    allow_fallback_to_placeholder: bool
    default_model: str | None
    default_embedding_model: str | None
    startup_timeout_seconds: int
    models: list[RuntimeModelConfig]
    local_openai: LocalOpenAIProviderConfig


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
class RagChunkingConfig:
    chunk_size: int
    chunk_overlap: int


@dataclass(frozen=True)
class RagIndexConfig:
    directory: str
    vectors_db_filename: str
    documents_filename: str
    metadata_filename: str


@dataclass(frozen=True)
class RagRetrievalConfig:
    top_k: int
    similarity_metric: str
    min_similarity: float


@dataclass(frozen=True)
class RagConfig:
    enabled: bool
    default_embedding_model: str | None
    chunking: RagChunkingConfig
    index: RagIndexConfig
    retrieval: RagRetrievalConfig


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
    rag: RagConfig
    placeholders: PlaceholderConfig
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
