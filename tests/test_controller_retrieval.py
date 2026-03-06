import json
import logging
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.config import load_config
from backend.controller import ControllerRequestError, ControllerService
from backend.rag.vector_store import IndexedDocument, SQLiteVectorStore, VectorRecord
from backend.runtime import EmbeddingGenerationRequest, PlaceholderRuntime, RuntimeManager


class ControllerRetrievalTests(unittest.TestCase):
    def _build_controller(self, config, vector_store: SQLiteVectorStore | None = None) -> ControllerService:
        runtime = RuntimeManager(
            primary_backend=PlaceholderRuntime(config.runtime),
            fallback_backend=None,
            selected_provider="placeholder",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
        runtime.startup()

        return ControllerService(
            config=config,
            runtime_manager=runtime,
            logger=logging.getLogger("test.controller"),
            startup_state={
                "config_loaded": True,
                "logging_initialized": True,
                "runtime_initialized": True,
                "controller_initialized": True,
                "api_initialized": True,
            },
            rag_vector_store=vector_store,
        )

    def test_controller_retrieval_search_returns_results(self) -> None:
        config = load_config()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteVectorStore(index_directory=tmpdir)
            store.initialize()
            controller = self._build_controller(config, vector_store=store)

            embeddings = controller.create_embeddings(
                EmbeddingGenerationRequest(
                    model="local-embedding",
                    input_texts=["system architecture"],
                    request_id="req_embed_seed",
                )
            )
            vector = embeddings["data"][0]["embedding"]

            store.upsert_document(
                IndexedDocument(
                    document_id="doc_ret_1",
                    source_file="/tmp/sample.txt",
                    chunk_count=1,
                    embedding_model="local-embedding",
                    indexed_at_utc=datetime.now(timezone.utc).isoformat(),
                ),
                [
                    VectorRecord(
                        document_id="doc_ret_1",
                        chunk_index=0,
                        embedding=vector,
                        chunk_text="System architecture routes through the controller.",
                        text_length=49,
                        metadata={"document_id": "doc_ret_1", "chunk_index": 0},
                    )
                ],
            )

            response = controller.search_retrieval(query="system architecture", top_k=3)
            self.assertGreaterEqual(response["result_count"], 1)
            self.assertIn("controller", response["results"][0]["chunk_text"].lower())

    def test_controller_retrieval_search_rejected_when_rag_disabled(self) -> None:
        base = json.loads(Path("config/portable-ai-drive-pro.json").read_text(encoding="utf-8"))
        base["rag"]["enabled"] = False
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp.write(json.dumps(base))
            tmp_path = Path(tmp.name)
        try:
            config = load_config(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        controller = self._build_controller(config, vector_store=None)

        with self.assertRaises(ControllerRequestError) as err:
            controller.search_retrieval(query="architecture")

        self.assertEqual(err.exception.error_type, "rag_disabled")


if __name__ == "__main__":
    unittest.main()
