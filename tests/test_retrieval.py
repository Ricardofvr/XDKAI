import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.config import load_config
from backend.rag.retrieval import RetrievalService, main
from backend.rag.vector_store import IndexedDocument, SQLiteVectorStore, VectorRecord


class _FakeController:
    def create_embeddings(self, request):
        query = request.input_texts[0].lower()
        if "architecture" in query:
            vector = [1.0, 0.0]
        elif "storage" in query:
            vector = [0.0, 1.0]
        else:
            vector = [0.5, 0.5]

        return {
            "object": "list",
            "data": [{"object": "embedding", "index": 0, "embedding": vector}],
            "model": request.model,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }


class RetrievalServiceTests(unittest.TestCase):
    def _build_store_with_vectors(self, index_directory: Path) -> SQLiteVectorStore:
        store = SQLiteVectorStore(index_directory=index_directory)
        store.initialize()

        now = datetime.now(timezone.utc).isoformat()
        document = IndexedDocument(
            document_id="doc1",
            source_file="/tmp/sample.txt",
            chunk_count=2,
            embedding_model="local-embedding",
            indexed_at_utc=now,
        )
        store.upsert_document(
            document,
            [
                VectorRecord(
                    document_id="doc1",
                    chunk_index=0,
                    embedding=[1.0, 0.0],
                    chunk_text="System architecture routes requests through the controller.",
                    text_length=58,
                    metadata={"document_id": "doc1", "chunk_index": 0, "text_length": 58},
                ),
                VectorRecord(
                    document_id="doc1",
                    chunk_index=1,
                    embedding=[0.0, 1.0],
                    chunk_text="Vector storage persists embeddings for retrieval.",
                    text_length=47,
                    metadata={"document_id": "doc1", "chunk_index": 1, "text_length": 47},
                ),
            ],
        )
        return store

    def test_retrieval_returns_ranked_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = self._build_store_with_vectors(Path(tmpdir) / "index")
            service = RetrievalService(
                controller=_FakeController(),
                vector_store=store,
                logger=logging.getLogger("test.rag.retrieval"),
                default_embedding_model="local-embedding",
                default_top_k=3,
                similarity_metric="cosine",
                default_min_similarity=0.0,
            )

            response = service.search("What does the architecture do?", top_k=2)
            self.assertEqual(response.result_count, 2)
            self.assertGreaterEqual(response.results[0].similarity, response.results[1].similarity)
            self.assertEqual(response.results[0].chunk_index, 0)
            self.assertIn("controller", response.results[0].chunk_text.lower())

    def test_retrieval_handles_empty_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteVectorStore(index_directory=Path(tmpdir) / "index")
            store.initialize()
            service = RetrievalService(
                controller=_FakeController(),
                vector_store=store,
                logger=logging.getLogger("test.rag.retrieval"),
                default_embedding_model="local-embedding",
                default_top_k=3,
                similarity_metric="cosine",
                default_min_similarity=0.0,
            )

            response = service.search("architecture")
            self.assertEqual(response.result_count, 0)
            self.assertEqual(response.results, [])

    def test_retrieval_rejects_invalid_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteVectorStore(index_directory=Path(tmpdir) / "index")
            store.initialize()
            service = RetrievalService(
                controller=_FakeController(),
                vector_store=store,
                logger=logging.getLogger("test.rag.retrieval"),
                default_embedding_model="local-embedding",
                default_top_k=3,
                similarity_metric="cosine",
                default_min_similarity=0.0,
            )

            with self.assertRaises(ValueError):
                service.search("   ")


@dataclass
class _FakeCore:
    config: object
    controller: object
    vector_store: SQLiteVectorStore
    shutdown_called: bool = False

    def shutdown(self) -> None:
        self.shutdown_called = True


class RetrievalCliTests(unittest.TestCase):
    def test_cli_search_command_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = json.loads(Path("config/portable-ai-drive-pro.json").read_text(encoding="utf-8"))
            config_data["rag"]["index"]["directory"] = str(Path(tmpdir) / "index")

            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config_data), encoding="utf-8")
            config = load_config(config_path)

            store = SQLiteVectorStore(index_directory=config.rag.index.directory)
            store.initialize()

            now = datetime.now(timezone.utc).isoformat()
            store.upsert_document(
                IndexedDocument(
                    document_id="doc_cli",
                    source_file="/tmp/cli.txt",
                    chunk_count=1,
                    embedding_model="local-embedding",
                    indexed_at_utc=now,
                ),
                [
                    VectorRecord(
                        document_id="doc_cli",
                        chunk_index=0,
                        embedding=[1.0, 0.0],
                        chunk_text="Vector store architecture details.",
                        text_length=32,
                        metadata={"document_id": "doc_cli", "chunk_index": 0, "text_length": 32},
                    )
                ],
            )

            fake_core = _FakeCore(
                config=config,
                controller=_FakeController(),
                vector_store=store,
            )

            stdout = io.StringIO()
            with patch("backend.bootstrap.bootstrap_core", return_value=fake_core):
                with redirect_stdout(stdout):
                    exit_code = main(["search", "architecture", "--json"])

            self.assertEqual(exit_code, 0)
            self.assertTrue(fake_core.shutdown_called)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["query"], "architecture")
            self.assertGreaterEqual(payload["result_count"], 1)
            self.assertIn("similarity", payload["results"][0])


if __name__ == "__main__":
    unittest.main()
