import json
import logging
import tempfile
import unittest
from pathlib import Path

from backend.config import load_config
from backend.controller import ControllerService
from backend.rag.retrieval import RetrievalHit, RetrievalResponse
from backend.runtime import RuntimeManager
from backend.runtime.interfaces import (
    ChatGenerationChoice,
    ChatGenerationRequest,
    ChatGenerationResponse,
    ChatMessage,
    EmbeddingGenerationRequest,
    EmbeddingGenerationResponse,
    EmbeddingVector,
    ModelInfo,
    RuntimeStatus,
)


def _load_mutated_config(mutation_fn):
    base = json.loads(Path("config/portable-ai-drive-pro.json").read_text(encoding="utf-8"))
    mutation_fn(base)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write(json.dumps(base))
        tmp_path = Path(tmp.name)
    try:
        return load_config(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


class _CapturingRuntimeBackend:
    def __init__(self) -> None:
        self.last_chat_request: ChatGenerationRequest | None = None

    def startup(self) -> None:
        return

    def shutdown(self) -> None:
        return

    def get_status(self) -> RuntimeStatus:
        return RuntimeStatus(
            state="ready",
            provider="placeholder",
            mode="placeholder",
            initialized=True,
            ready=True,
            generation_ready=True,
            embedding_ready=True,
            provider_reachable=True,
            active_model="local-general",
            models_available=["local-general", "local-embedding"],
            details={},
        )

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="local-general", role="general", provider_model_id="qwen2.5-32b-general"),
            ModelInfo(id="local-embedding", role="embedding", provider_model_id="nomic-embed-text"),
        ]

    def list_configured_models(self) -> list[ModelInfo]:
        return self.list_models()

    def get_metadata(self) -> dict:
        return {"provider": "placeholder"}

    def generate_chat(self, request: ChatGenerationRequest) -> ChatGenerationResponse:
        self.last_chat_request = request
        return ChatGenerationResponse(
            model=request.model,
            choices=[
                ChatGenerationChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content="rag-aware-response"),
                    finish_reason="stop",
                )
            ],
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    def stream_chat(self, request: ChatGenerationRequest):
        raise NotImplementedError

    def generate_embeddings(self, request: EmbeddingGenerationRequest) -> EmbeddingGenerationResponse:
        return EmbeddingGenerationResponse(
            model=request.model,
            data=[EmbeddingVector(index=0, embedding=[0.1, 0.2])],
            usage={"prompt_tokens": 0, "total_tokens": 0},
        )


class _FakeRetrievalService:
    def __init__(self, response: RetrievalResponse | None = None, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc
        self.calls: list[str] = []

    def search(self, query: str, top_k: int | None = None, embedding_model: str | None = None, min_similarity: float | None = None):
        self.calls.append(query)
        if self._exc is not None:
            raise self._exc
        return self._response


class RagChatIntegrationTests(unittest.TestCase):
    def _build_controller(self, config, retrieval_service) -> tuple[ControllerService, _CapturingRuntimeBackend]:
        backend = _CapturingRuntimeBackend()
        runtime_manager = RuntimeManager(
            primary_backend=backend,
            fallback_backend=None,
            selected_provider="placeholder",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
        runtime_manager.startup()

        controller = ControllerService(
            config=config,
            runtime_manager=runtime_manager,
            logger=logging.getLogger("test.controller"),
            startup_state={
                "config_loaded": True,
                "logging_initialized": True,
                "runtime_initialized": True,
                "controller_initialized": True,
                "api_initialized": True,
            },
            rag_retrieval_service=retrieval_service,
        )
        return controller, backend

    def test_chat_injects_retrieved_context_when_enabled(self) -> None:
        config = _load_mutated_config(lambda data: data["rag"]["chat"].update({"enabled": True, "debug_retrieval": False}))
        retrieval_response = RetrievalResponse(
            query="Explain architecture",
            embedding_model="local-embedding",
            similarity_metric="cosine",
            top_k=3,
            min_similarity=-1.0,
            result_count=1,
            results=[
                RetrievalHit(
                    rank=1,
                    similarity=0.91,
                    document_id="doc1",
                    source_file="/tmp/sample.txt",
                    chunk_index=0,
                    chunk_text="Architecture uses controller orchestration.",
                    chunk_preview="Architecture uses controller orchestration.",
                    text_length=41,
                    metadata={"document_id": "doc1", "chunk_index": 0},
                )
            ],
        )
        retrieval_service = _FakeRetrievalService(response=retrieval_response)
        controller, backend = self._build_controller(config, retrieval_service)

        request = ChatGenerationRequest(
            model="local-general",
            messages=[ChatMessage(role="user", content="Explain architecture")],
            stream=False,
            request_id="req_rag_1",
        )

        response = controller.create_chat_completion(request)

        self.assertEqual(response["choices"][0]["message"]["content"], "rag-aware-response")
        self.assertIn("portable_ai", response)
        self.assertTrue(response["portable_ai"]["session_id"])
        self.assertIn("grounding", response["portable_ai"])
        self.assertTrue(response["portable_ai"]["grounding"]["retrieval_used"])
        self.assertEqual(response["portable_ai"]["grounding"]["source_count"], 1)
        self.assertEqual(response["portable_ai"]["grounding"]["injected_chunk_count"], 1)
        self.assertEqual(retrieval_service.calls, ["Explain architecture"])
        self.assertIsNotNone(backend.last_chat_request)
        assert backend.last_chat_request is not None
        self.assertEqual(len(backend.last_chat_request.messages), 3)
        self.assertEqual(backend.last_chat_request.messages[0].role, "system")
        self.assertIn("Portable AI Drive PRO", backend.last_chat_request.messages[0].content)
        self.assertIn("BEGIN_RETRIEVED_CONTEXT", backend.last_chat_request.messages[1].content)
        self.assertEqual(backend.last_chat_request.messages[2].content, "Explain architecture")

    def test_chat_skips_retrieval_when_disabled(self) -> None:
        config = _load_mutated_config(lambda data: data["rag"]["chat"].update({"enabled": False}))
        retrieval_service = _FakeRetrievalService(
            response=RetrievalResponse(
                query="ignored",
                embedding_model="local-embedding",
                similarity_metric="cosine",
                top_k=3,
                min_similarity=-1.0,
                result_count=0,
                results=[],
            )
        )
        controller, backend = self._build_controller(config, retrieval_service)

        request = ChatGenerationRequest(
            model="local-general",
            messages=[ChatMessage(role="user", content="No retrieval please")],
            stream=False,
            request_id="req_rag_2",
        )

        response = controller.create_chat_completion(request)

        self.assertEqual(retrieval_service.calls, [])
        assert backend.last_chat_request is not None
        self.assertEqual(len(backend.last_chat_request.messages), 2)
        self.assertIn("portable_ai", response)
        self.assertFalse(response["portable_ai"]["grounding"]["retrieval_used"])

    def test_chat_falls_back_when_retrieval_errors(self) -> None:
        config = _load_mutated_config(lambda data: data["rag"]["chat"].update({"enabled": True}))
        retrieval_service = _FakeRetrievalService(exc=RuntimeError("search failure"))
        controller, backend = self._build_controller(config, retrieval_service)

        request = ChatGenerationRequest(
            model="local-general",
            messages=[ChatMessage(role="user", content="Explain architecture")],
            stream=False,
            request_id="req_rag_3",
        )

        controller.create_chat_completion(request)

        assert backend.last_chat_request is not None
        self.assertEqual(len(backend.last_chat_request.messages), 2)
        self.assertEqual(backend.last_chat_request.messages[-1].content, "Explain architecture")

    def test_chat_debug_mode_includes_rag_debug_payload(self) -> None:
        config = _load_mutated_config(lambda data: data["rag"]["chat"].update({"enabled": True, "debug_retrieval": True}))
        retrieval_response = RetrievalResponse(
            query="Explain architecture",
            embedding_model="local-embedding",
            similarity_metric="cosine",
            top_k=3,
            min_similarity=-1.0,
            result_count=1,
            results=[
                RetrievalHit(
                    rank=1,
                    similarity=0.82,
                    document_id="doc1",
                    source_file="/tmp/sample.txt",
                    chunk_index=0,
                    chunk_text="Architecture context",
                    chunk_preview="Architecture context",
                    text_length=20,
                    metadata={"document_id": "doc1", "chunk_index": 0},
                )
            ],
        )
        retrieval_service = _FakeRetrievalService(response=retrieval_response)
        controller, _ = self._build_controller(config, retrieval_service)

        request = ChatGenerationRequest(
            model="local-general",
            messages=[ChatMessage(role="user", content="Explain architecture")],
            stream=False,
            request_id="req_rag_4",
        )

        response = controller.create_chat_completion(request)
        self.assertIn("rag_debug", response)
        self.assertIn("portable_ai", response)
        self.assertIn("session_debug", response["portable_ai"])
        self.assertTrue(response["rag_debug"]["retrieval_triggered"])
        self.assertTrue(response["rag_debug"]["retrieval_used"])
        self.assertEqual(response["rag_debug"]["retrieval_result_count_raw"], 1)
        self.assertEqual(response["rag_debug"]["retrieval_result_count_injected"], 1)
        self.assertIn("postprocess", response["rag_debug"])
        self.assertIn("source_distribution", response["rag_debug"])

    def test_chat_falls_back_when_retrieval_results_filtered_out(self) -> None:
        def mutate(data):
            data["rag"]["chat"].update({"enabled": True, "debug_retrieval": True, "min_similarity": 0.95})

        config = _load_mutated_config(mutate)
        retrieval_response = RetrievalResponse(
            query="Explain architecture",
            embedding_model="local-embedding",
            similarity_metric="cosine",
            top_k=3,
            min_similarity=-1.0,
            result_count=1,
            results=[
                RetrievalHit(
                    rank=1,
                    similarity=0.82,
                    document_id="doc1",
                    source_file="/tmp/sample.txt",
                    chunk_index=0,
                    chunk_text="Architecture context",
                    chunk_preview="Architecture context",
                    text_length=20,
                    metadata={"document_id": "doc1", "chunk_index": 0},
                )
            ],
        )
        retrieval_service = _FakeRetrievalService(response=retrieval_response)
        controller, backend = self._build_controller(config, retrieval_service)

        request = ChatGenerationRequest(
            model="local-general",
            messages=[ChatMessage(role="user", content="Explain architecture")],
            stream=False,
            request_id="req_rag_5",
        )

        response = controller.create_chat_completion(request)
        assert backend.last_chat_request is not None
        self.assertEqual(len(backend.last_chat_request.messages), 2)
        self.assertFalse(response["rag_debug"]["retrieval_used"])
        self.assertEqual(response["rag_debug"]["skipped_reason"], "retrieval_results_filtered_empty")

    def test_grounding_summary_can_be_disabled(self) -> None:
        def mutate(data):
            data["chat"]["grounding"]["include_summary"] = False

        config = _load_mutated_config(mutate)
        retrieval_service = _FakeRetrievalService(response=None)
        controller, _ = self._build_controller(config, retrieval_service)

        response = controller.create_chat_completion(
            ChatGenerationRequest(
                model="local-general",
                messages=[ChatMessage(role="user", content="hello")],
                stream=False,
                request_id="req_grounding_disabled",
            )
        )

        self.assertIn("portable_ai", response)
        self.assertNotIn("grounding", response["portable_ai"])

    def test_grounding_debug_details_can_be_enabled(self) -> None:
        def mutate(data):
            data["chat"]["grounding"]["include_debug_details"] = True
            data["rag"]["chat"]["enabled"] = False

        config = _load_mutated_config(mutate)
        retrieval_service = _FakeRetrievalService(response=None)
        controller, _ = self._build_controller(config, retrieval_service)

        response = controller.create_chat_completion(
            ChatGenerationRequest(
                model="local-general",
                messages=[ChatMessage(role="user", content="hello")],
                stream=False,
                request_id="req_grounding_debug",
            )
        )

        self.assertIn("portable_ai", response)
        self.assertIn("grounding_debug", response["portable_ai"])

    def test_chat_reuses_session_history_on_follow_up_turn(self) -> None:
        config = _load_mutated_config(lambda data: data["rag"]["chat"].update({"enabled": False}))
        retrieval_service = _FakeRetrievalService(response=None)
        controller, backend = self._build_controller(config, retrieval_service)

        first_response = controller.create_chat_completion(
            ChatGenerationRequest(
                model="local-general",
                messages=[ChatMessage(role="user", content="First question")],
                stream=False,
                request_id="req_session_1",
            )
        )
        session_id = first_response["portable_ai"]["session_id"]

        controller.create_chat_completion(
            ChatGenerationRequest(
                model="local-general",
                messages=[ChatMessage(role="user", content="Follow-up question")],
                stream=False,
                request_id="req_session_2",
                session_id=session_id,
            )
        )

        assert backend.last_chat_request is not None
        contents = [message.content for message in backend.last_chat_request.messages]
        self.assertIn("First question", contents)
        self.assertIn("rag-aware-response", contents)
        self.assertIn("Follow-up question", contents)

    def test_session_compaction_recommendation_exposed(self) -> None:
        def mutate(data):
            data["rag"]["chat"]["enabled"] = False
            data["chat"]["summarisation"]["enabled"] = True
            data["chat"]["summarisation"]["trigger_turn_count"] = 1
            data["chat"]["summarisation"]["trigger_character_count"] = 999999

        config = _load_mutated_config(mutate)
        retrieval_service = _FakeRetrievalService(response=None)
        controller, _ = self._build_controller(config, retrieval_service)

        response = controller.create_chat_completion(
            ChatGenerationRequest(
                model="local-general",
                messages=[ChatMessage(role="user", content="hello")],
                stream=False,
                request_id="req_compact_1",
            )
        )

        self.assertIn("portable_ai", response)
        self.assertIn("session_compaction", response["portable_ai"])
        self.assertTrue(response["portable_ai"]["session_compaction"]["recommended"])


if __name__ == "__main__":
    unittest.main()
