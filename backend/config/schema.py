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
class ChatSessionConfig:
    directory: str
    persist_to_disk: bool


@dataclass(frozen=True)
class ChatHistoryConfig:
    max_turns: int
    max_characters: int
    retain_system_prompt: bool


@dataclass(frozen=True)
class ChatSystemPromptConfig:
    text: str


@dataclass(frozen=True)
class ChatConfig:
    include_session_metadata: bool
    debug_session: bool
    session: ChatSessionConfig
    history: ChatHistoryConfig
    system_prompt: ChatSystemPromptConfig


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
class RagChatConfig:
    enabled: bool
    retrieval_fetch_k: int
    max_context_chunks: int
    max_context_characters: int
    max_chunks_per_document: int
    deduplicate_results: bool
    near_duplicate_threshold: float
    min_similarity: float
    context_prefix: str
    include_source_metadata: bool
    debug_retrieval: bool


@dataclass(frozen=True)
class RagConfig:
    enabled: bool
    default_embedding_model: str | None
    chunking: RagChunkingConfig
    index: RagIndexConfig
    retrieval: RagRetrievalConfig
    chat: RagChatConfig


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
    chat: ChatConfig
    rag: RagConfig
    placeholders: PlaceholderConfig
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
