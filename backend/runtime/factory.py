from __future__ import annotations

import logging

from backend.config.schema import RuntimeConfig

from .interfaces import RuntimeBackend
from .placeholder import PlaceholderRuntime
from .providers import LocalOpenAIRuntime


def _create_backend(provider: str, config: RuntimeConfig, logger: logging.Logger) -> RuntimeBackend:
    if provider == "placeholder":
        return PlaceholderRuntime(config)
    if provider == "local_openai":
        return LocalOpenAIRuntime(config, logger.getChild("local_openai"))
    raise ValueError(f"Unsupported runtime provider '{provider}'.")


def build_runtime_backends(
    config: RuntimeConfig,
    logger: logging.Logger,
) -> tuple[RuntimeBackend, RuntimeBackend | None]:
    primary = _create_backend(config.provider, config, logger)

    fallback: RuntimeBackend | None = None
    if config.allow_fallback_to_placeholder and config.provider != "placeholder":
        fallback_provider = config.fallback_provider or "placeholder"
        fallback = _create_backend(fallback_provider, config, logger)

    return primary, fallback
