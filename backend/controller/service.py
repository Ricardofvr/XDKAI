from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from backend.config.schema import AppConfig
from backend.rag.context_builder import build_context_text, inject_context_before_latest_user
from backend.rag.retrieval import RetrievalService
from backend.rag.retrieval_postprocessing import (
    RetrievalPostprocessConfig,
    postprocess_retrieval_hits,
)
from backend.runtime.interfaces import (
    ChatGenerationRequest,
    ChatMessage,
    EmbeddingGenerationRequest,
    RuntimeInvocationError,
    RuntimeUnavailableError,
)
from backend.runtime.manager import RuntimeManager

from .errors import ControllerRequestError


class ControllerService:
    """Central orchestration boundary for API-facing requests."""

    def __init__(
        self,
        config: AppConfig,
        runtime_manager: RuntimeManager,
        logger: logging.Logger,
        startup_state: dict[str, bool],
        rag_vector_store: Any | None = None,
        rag_retrieval_service: Any | None = None,
    ) -> None:
        self._config = config
        self._runtime_manager = runtime_manager
        self._logger = logger
        self._startup_state = startup_state
        self._rag_vector_store = rag_vector_store
        self._rag_retrieval_service = rag_retrieval_service
        self._rag_diagnostics_lock = Lock()
        self._last_rag_diagnostics: dict[str, Any] | None = None

        # Week 2 placeholders for future orchestrated subsystems.
        self._policy_manager = None
        self._tool_dispatcher = None
        self._memory_manager = None
        self._research_manager = None

        if self._rag_retrieval_service is None and self._rag_vector_store is not None:
            self._rag_retrieval_service = self._build_retrieval_service()

    def get_health(self) -> dict[str, Any]:
        runtime_status = self._runtime_manager.get_status_payload()
        runtime_ready = bool(runtime_status.get("ready"))
        status = "ok" if runtime_ready else "degraded"

        return {
            "status": status,
            "service": self._config.app.name,
            "subsystems": {
                "controller": "ready",
                "runtime": runtime_status.get("state"),
                "config": "loaded",
            },
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def get_version_info(self) -> dict[str, Any]:
        return {
            "name": self._config.app.name,
            "version": self._config.app.version,
            "environment": self._config.app.environment,
        }

    def get_system_status(self) -> dict[str, Any]:
        runtime_status = self._runtime_manager.get_status_payload()
        rag_index_status = self._get_rag_index_status(runtime_status=runtime_status)
        rag_chat_status = self._get_rag_chat_status(rag_index_status=rag_index_status)
        return {
            "startup_state": self._startup_state,
            "environment": self._config.app.environment,
            "offline_mode": self._config.operating_mode.offline_default,
            "runtime": runtime_status,
            "runtime_metadata": self._runtime_manager.get_metadata(),
            "model_registry": self._runtime_manager.get_model_registry_payload(),
            "rag_index": rag_index_status,
            "rag_chat": rag_chat_status,
            "feature_flags": {
                "openai_compatible_api": self._config.feature_flags.openai_compatible_api,
                "tool_execution": self._config.feature_flags.tool_execution,
                "memory": self._config.feature_flags.memory,
                "research": self._config.feature_flags.research,
            },
            "future_modules": {
                "policy_validation": "deferred",
                "tool_dispatch": "deferred",
                "memory_manager": "deferred",
                "research_manager": "deferred",
            },
        }

    def mark_startup_step(self, step_name: str, completed: bool = True) -> None:
        self._startup_state[step_name] = completed

    def _build_retrieval_service(self) -> RetrievalService | None:
        if not self._config.rag.enabled:
            return None

        try:
            return RetrievalService(
                controller=self,
                vector_store=self._rag_vector_store,
                logger=self._logger.getChild("rag.retrieval"),
                default_embedding_model=self._config.rag.default_embedding_model or "",
                default_top_k=self._config.rag.retrieval.top_k,
                similarity_metric=self._config.rag.retrieval.similarity_metric,
                default_min_similarity=self._config.rag.retrieval.min_similarity,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.exception(
                "controller_rag_retrieval_service_init_failed",
                extra={
                    "event": "controller_rag",
                    "error": str(exc),
                },
            )
            return None

    def _get_rag_index_status(self, runtime_status: dict[str, Any]) -> dict[str, Any]:
        if self._rag_vector_store is None:
            return {
                "enabled": False,
                "initialized": False,
                "documents_indexed": 0,
                "total_vectors": 0,
                "embedding_models": [],
                "index_location": None,
                "search_enabled": False,
                "embedding_model": self._config.rag.default_embedding_model,
                "total_documents": 0,
                "last_indexed_at": None,
            }

        try:
            status = self._rag_vector_store.get_status_payload()
            documents_indexed = int(status.get("documents_indexed", 0))
            total_vectors = int(status.get("total_vectors", 0))
            embedding_ready = bool(runtime_status.get("embedding_ready"))
            search_enabled = bool(
                self._config.rag.enabled
                and embedding_ready
                and status.get("initialized")
                and total_vectors > 0
            )
            return {
                "enabled": bool(self._config.rag.enabled),
                **status,
                "default_embedding_model": self._config.rag.default_embedding_model,
                "embedding_model": self._config.rag.default_embedding_model,
                "total_documents": documents_indexed,
                "last_indexed_at": status.get("last_indexed_at_utc"),
                "search_enabled": search_enabled,
                "retrieval": {
                    "top_k": self._config.rag.retrieval.top_k,
                    "similarity_metric": self._config.rag.retrieval.similarity_metric,
                    "min_similarity": self._config.rag.retrieval.min_similarity,
                },
            }
        except Exception as exc:  # noqa: BLE001
            self._logger.exception(
                "controller_rag_status_failed",
                extra={
                    "event": "controller_status",
                    "error": str(exc),
                },
            )
            return {
                "enabled": bool(self._config.rag.enabled),
                "initialized": False,
                "documents_indexed": 0,
                "total_vectors": 0,
                "embedding_models": [],
                "index_location": self._config.rag.index.directory,
                "error": str(exc),
                "search_enabled": False,
                "embedding_model": self._config.rag.default_embedding_model,
                "total_documents": 0,
                "last_indexed_at": None,
                "retrieval": {
                    "top_k": self._config.rag.retrieval.top_k,
                    "similarity_metric": self._config.rag.retrieval.similarity_metric,
                    "min_similarity": self._config.rag.retrieval.min_similarity,
                },
            }

    def _get_rag_chat_status(self, rag_index_status: dict[str, Any]) -> dict[str, Any]:
        index_ready = bool(rag_index_status.get("initialized")) and int(rag_index_status.get("total_vectors", 0)) > 0
        retrieval_enabled = bool(
            self._config.rag.enabled
            and self._config.rag.chat.enabled
            and rag_index_status.get("search_enabled")
            and self._rag_retrieval_service is not None
        )
        with self._rag_diagnostics_lock:
            last_diagnostics = dict(self._last_rag_diagnostics) if self._last_rag_diagnostics else None

        return {
            "enabled": bool(self._config.rag.chat.enabled),
            "retrieval_fetch_k": self._config.rag.chat.retrieval_fetch_k,
            "max_context_chunks": self._config.rag.chat.max_context_chunks,
            "max_context_characters": self._config.rag.chat.max_context_characters,
            "max_chunks_per_document": self._config.rag.chat.max_chunks_per_document,
            "deduplicate_results": self._config.rag.chat.deduplicate_results,
            "near_duplicate_threshold": self._config.rag.chat.near_duplicate_threshold,
            "min_similarity": self._config.rag.chat.min_similarity,
            "index_ready": index_ready,
            "retrieval_enabled": retrieval_enabled,
            "include_source_metadata": self._config.rag.chat.include_source_metadata,
            "debug_retrieval": self._config.rag.chat.debug_retrieval,
            "last_retrieval_diagnostics": last_diagnostics,
        }

    def list_models(self) -> dict[str, Any]:
        self._logger.info("controller_list_models", extra={"event": "controller_route", "route": "list_models"})
        models = self._runtime_manager.list_models()
        return {
            "object": "list",
            "data": [
                {
                    "id": model.id,
                    "object": model.object,
                    "created": model.created,
                    "owned_by": model.owned_by,
                }
                for model in models
            ],
        }

    def create_chat_completion(self, request: ChatGenerationRequest) -> dict[str, Any]:
        self._logger.info(
            "controller_chat_completion_received",
            extra={
                "event": "controller_route",
                "route": "chat_completions",
                "model": request.model,
                "stream": request.stream,
                "request_id": request.request_id,
            },
        )

        if request.stream:
            raise ControllerRequestError(
                "stream=true is not implemented yet.",
                error_type="unsupported_feature",
                status_code=400,
            )

        available_models = {model.id for model in self._runtime_manager.list_generation_models()}
        if request.model not in available_models:
            raise ControllerRequestError(
                f"Model '{request.model}' is not available for chat generation.",
                error_type="model_not_found",
                status_code=404,
            )

        runtime_request = request
        rag_debug: dict[str, Any] = {
            "retrieval_triggered": False,
            "retrieval_used": False,
            "retrieval_result_count_raw": 0,
            "retrieval_result_count_filtered": 0,
            "retrieval_result_count_injected": 0,
            "postprocess": None,
            "chunks": [],
            "skipped_reason": None,
            "error": None,
        }

        if self._config.rag.enabled and self._config.rag.chat.enabled and self._rag_retrieval_service is not None:
            latest_user = self._extract_latest_user_message(request.messages)
            if latest_user is not None:
                rag_debug["retrieval_triggered"] = True
                retrieval_top_k = max(
                    self._config.rag.chat.retrieval_fetch_k,
                    self._config.rag.chat.max_context_chunks,
                )
                self._logger.info(
                    "controller_rag_retrieval_triggered",
                    extra={
                        "event": "controller_rag",
                        "request_id": request.request_id,
                        "query_length": len(latest_user.content),
                        "max_context_chunks": self._config.rag.chat.max_context_chunks,
                        "retrieval_top_k": retrieval_top_k,
                    },
                )

                try:
                    retrieval_response = self._rag_retrieval_service.search(
                        query=latest_user.content,
                        top_k=retrieval_top_k,
                    )
                    rag_debug["retrieval_result_count_raw"] = retrieval_response.result_count
                    processed = postprocess_retrieval_hits(
                        retrieval_response.results,
                        RetrievalPostprocessConfig(
                            min_similarity=self._config.rag.chat.min_similarity,
                            deduplicate_results=self._config.rag.chat.deduplicate_results,
                            near_duplicate_threshold=self._config.rag.chat.near_duplicate_threshold,
                            max_chunks_per_document=self._config.rag.chat.max_chunks_per_document,
                            max_context_chunks=self._config.rag.chat.max_context_chunks,
                            max_context_characters=self._config.rag.chat.max_context_characters,
                        ),
                    )
                    postprocess_payload = asdict(processed.diagnostics)
                    rag_debug["postprocess"] = postprocess_payload
                    rag_debug["retrieval_result_count_filtered"] = processed.diagnostics.post_filter_count
                    rag_debug["retrieval_result_count_injected"] = processed.diagnostics.output_count
                    self._record_rag_diagnostics(
                        request_id=request.request_id,
                        diagnostics=postprocess_payload,
                    )

                    if processed.hits:
                        selected_hits = processed.hits
                        context_text = build_context_text(
                            hits=selected_hits,
                            context_prefix=self._config.rag.chat.context_prefix,
                            include_source_metadata=self._config.rag.chat.include_source_metadata,
                        )
                        augmented_messages = inject_context_before_latest_user(
                            messages=request.messages,
                            context_text=context_text,
                        )
                        runtime_request = ChatGenerationRequest(
                            model=request.model,
                            messages=augmented_messages,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                            stream=request.stream,
                            request_id=request.request_id,
                        )
                        rag_debug["retrieval_used"] = True
                        rag_debug["chunks"] = [
                            {
                                "source_file": hit.source_file,
                                "document_id": hit.document_id,
                                "chunk_index": hit.chunk_index,
                                "similarity": round(hit.similarity, 4),
                                "text_length": hit.text_length,
                                "truncated": bool(hit.metadata.get("truncated", False)),
                            }
                            for hit in selected_hits
                        ]
                        self._logger.info(
                            "controller_rag_context_injected",
                            extra={
                                "event": "controller_rag",
                                "request_id": request.request_id,
                                "result_count_raw": retrieval_response.result_count,
                                "result_count_filtered": processed.diagnostics.post_filter_count,
                                "injected_chunks": len(selected_hits),
                                "injected_characters": processed.diagnostics.output_characters,
                                "duplicate_filtered_count": processed.diagnostics.duplicate_filtered_count,
                                "near_duplicate_filtered_count": processed.diagnostics.near_duplicate_filtered_count,
                                "per_document_filtered_count": processed.diagnostics.per_document_filtered_count,
                                "similarity_filtered_count": processed.diagnostics.similarity_filtered_count,
                                "budget_chunk_limit_applied": processed.diagnostics.budget_chunk_limit_applied,
                                "budget_character_limit_applied": processed.diagnostics.budget_character_limit_applied,
                                "budget_truncated_count": processed.diagnostics.budget_truncated_count,
                            },
                        )
                    else:
                        rag_debug["skipped_reason"] = "retrieval_results_filtered_empty"
                        self._logger.info(
                            "controller_rag_context_skipped",
                            extra={
                                "event": "controller_rag",
                                "request_id": request.request_id,
                                "reason": rag_debug["skipped_reason"],
                                "result_count_raw": retrieval_response.result_count,
                                "result_count_filtered": processed.diagnostics.post_filter_count,
                            },
                        )
                except Exception as exc:  # noqa: BLE001
                    rag_debug["error"] = str(exc)
                    rag_debug["skipped_reason"] = "retrieval_failed"
                    self._logger.warning(
                        "controller_rag_retrieval_failed",
                        extra={
                            "event": "controller_rag",
                            "request_id": request.request_id,
                            "error": str(exc),
                        },
                    )
            else:
                rag_debug["skipped_reason"] = "no_user_message"
                self._logger.info(
                    "controller_rag_skipped_no_user_message",
                    extra={
                        "event": "controller_rag",
                        "request_id": request.request_id,
                    },
                )
        elif not self._config.rag.enabled:
            rag_debug["skipped_reason"] = "rag_disabled"
        elif not self._config.rag.chat.enabled:
            rag_debug["skipped_reason"] = "rag_chat_disabled"
        elif self._rag_retrieval_service is None:
            rag_debug["skipped_reason"] = "retrieval_unavailable"

        if rag_debug["retrieval_triggered"] and not rag_debug["retrieval_used"] and rag_debug["postprocess"] is None:
            self._record_rag_diagnostics(
                request_id=request.request_id,
                diagnostics={
                    "input_count": rag_debug["retrieval_result_count_raw"],
                    "post_filter_count": rag_debug["retrieval_result_count_filtered"],
                    "output_count": rag_debug["retrieval_result_count_injected"],
                    "output_characters": 0,
                    "skipped_reason": rag_debug["skipped_reason"],
                },
            )

        try:
            runtime_response = self._runtime_manager.generate_chat(runtime_request)
        except RuntimeUnavailableError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_unavailable",
                status_code=503,
            ) from exc
        except RuntimeInvocationError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_invocation_error",
                status_code=502,
            ) from exc

        if not runtime_response.choices:
            raise ControllerRequestError(
                "Runtime returned no choices.",
                error_type="runtime_error",
                status_code=500,
            )

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created_ts = int(time.time())

        response: dict[str, Any] = {
            "id": completion_id,
            "object": "chat.completion",
            "created": created_ts,
            "model": runtime_response.model,
            "choices": [
                {
                    "index": choice.index,
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content,
                    },
                    "finish_reason": choice.finish_reason,
                }
                for choice in runtime_response.choices
            ],
            "usage": runtime_response.usage,
        }

        if self._config.rag.chat.debug_retrieval:
            response["rag_debug"] = rag_debug

        self._logger.info(
            "controller_chat_completion_ready",
            extra={
                "event": "controller_route",
                "route": "chat_completions",
                "request_id": request.request_id,
                "completion_id": completion_id,
                "rag_retrieval_used": rag_debug["retrieval_used"],
                "rag_result_count_raw": rag_debug["retrieval_result_count_raw"],
                "rag_result_count_injected": rag_debug["retrieval_result_count_injected"],
            },
        )

        return response

    def create_embeddings(self, request: EmbeddingGenerationRequest) -> dict[str, Any]:
        self._logger.info(
            "controller_embeddings_received",
            extra={
                "event": "controller_route",
                "route": "embeddings",
                "model": request.model,
                "input_count": len(request.input_texts),
                "request_id": request.request_id,
            },
        )

        available_models = {model.id for model in self._runtime_manager.list_embedding_models()}
        if request.model not in available_models:
            raise ControllerRequestError(
                f"Model '{request.model}' is not available for embeddings.",
                error_type="model_not_found",
                status_code=404,
            )

        try:
            runtime_response = self._runtime_manager.generate_embeddings(request)
        except RuntimeUnavailableError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_unavailable",
                status_code=503,
            ) from exc
        except RuntimeInvocationError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_invocation_error",
                status_code=502,
            ) from exc

        if not runtime_response.data:
            raise ControllerRequestError(
                "Runtime returned no embeddings.",
                error_type="runtime_error",
                status_code=500,
            )

        response = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "index": item.index,
                    "embedding": item.embedding,
                }
                for item in runtime_response.data
            ],
            "model": runtime_response.model,
            "usage": runtime_response.usage,
        }

        self._logger.info(
            "controller_embeddings_ready",
            extra={
                "event": "controller_route",
                "route": "embeddings",
                "request_id": request.request_id,
                "embedding_count": len(runtime_response.data),
            },
        )

        return response

    def search_retrieval(
        self,
        query: str,
        top_k: int | None = None,
        embedding_model: str | None = None,
        min_similarity: float | None = None,
    ) -> dict[str, Any]:
        self._logger.info(
            "controller_retrieval_search_received",
            extra={
                "event": "controller_route",
                "route": "internal_rag_search",
                "query_length": len(query) if isinstance(query, str) else None,
                "top_k": top_k,
            },
        )

        if not self._config.rag.enabled:
            raise ControllerRequestError(
                "RAG is disabled in configuration.",
                error_type="rag_disabled",
                status_code=503,
            )
        if self._rag_retrieval_service is None:
            raise ControllerRequestError(
                "Retrieval service is not available.",
                error_type="retrieval_unavailable",
                status_code=503,
            )

        try:
            response = self._rag_retrieval_service.search(
                query=query,
                top_k=top_k,
                embedding_model=embedding_model,
                min_similarity=min_similarity,
            )
        except ControllerRequestError:
            raise
        except ValueError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="invalid_request",
                status_code=400,
            ) from exc
        except RuntimeUnavailableError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_unavailable",
                status_code=503,
            ) from exc
        except RuntimeInvocationError as exc:
            raise ControllerRequestError(
                str(exc),
                error_type="runtime_invocation_error",
                status_code=502,
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise ControllerRequestError(
                f"Retrieval failed: {exc}",
                error_type="retrieval_failed",
                status_code=502,
            ) from exc

        return asdict(response)

    def _record_rag_diagnostics(self, request_id: str | None, diagnostics: dict[str, Any]) -> None:
        payload = {
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            **diagnostics,
        }
        with self._rag_diagnostics_lock:
            self._last_rag_diagnostics = payload

    def _extract_latest_user_message(self, messages: list[ChatMessage]) -> ChatMessage | None:
        for message in reversed(messages):
            if message.role == "user" and message.content.strip():
                return message
        return None

    def dispatch_tool(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Tool dispatch is deferred to Week 7+")

    def validate_policy(self, action: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Policy validation is deferred to Week 7+")
