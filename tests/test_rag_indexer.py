import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from backend.config import load_config
from backend.rag.indexer import RagIndexerService, main
from backend.rag.vector_store import SQLiteVectorStore


class _FakeController:
    def __init__(self) -> None:
        self.last_model = None
        self.last_input_count = 0

    def create_embeddings(self, request):
        self.last_model = request.model
        self.last_input_count = len(request.input_texts)
        data = []
        for index, text in enumerate(request.input_texts):
            data.append({"object": "embedding", "index": index, "embedding": [float(len(text)), float(index)]})
        return {
            "object": "list",
            "data": data,
            "model": request.model,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }


class RagIndexerServiceTests(unittest.TestCase):
    def test_index_file_chunks_embeds_and_stores_vectors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document_path = Path(tmpdir) / "sample.txt"
            document_path.write_text("A" * 1200, encoding="utf-8")

            store = SQLiteVectorStore(index_directory=Path(tmpdir) / "index")
            store.initialize()

            controller = _FakeController()
            service = RagIndexerService(
                controller=controller,
                vector_store=store,
                logger=logging.getLogger("test.rag.indexer"),
                default_embedding_model="local-embedding",
                default_chunk_size=500,
                default_chunk_overlap=100,
            )

            result = service.index_file(document_path)

            self.assertEqual(result.embedding_model, "local-embedding")
            self.assertEqual(result.chunk_count, 3)
            self.assertEqual(result.vector_count, 3)
            self.assertEqual(store.count_vectors(), 3)
            self.assertEqual(controller.last_model, "local-embedding")
            self.assertEqual(controller.last_input_count, 3)

    def test_index_file_requires_existing_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteVectorStore(index_directory=Path(tmpdir) / "index")
            store.initialize()
            service = RagIndexerService(
                controller=_FakeController(),
                vector_store=store,
                logger=logging.getLogger("test.rag.indexer"),
                default_embedding_model="local-embedding",
                default_chunk_size=400,
                default_chunk_overlap=50,
            )

            with self.assertRaises(ValueError):
                service.index_file(Path(tmpdir) / "missing.txt")


@dataclass
class _FakeCore:
    config: object
    controller: object
    vector_store: SQLiteVectorStore
    shutdown_called: bool = False

    def shutdown(self) -> None:
        self.shutdown_called = True


class RagIndexerCliTests(unittest.TestCase):
    def test_cli_index_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document_path = Path(tmpdir) / "sample.txt"
            document_path.write_text("hello world " * 60, encoding="utf-8")

            config_data = json.loads(Path("config/portable-ai-drive-pro.json").read_text(encoding="utf-8"))
            config_data["rag"]["index"]["directory"] = str(Path(tmpdir) / "index")

            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config_data), encoding="utf-8")
            config = load_config(config_path)

            store = SQLiteVectorStore(index_directory=config.rag.index.directory)
            store.initialize()

            fake_core = _FakeCore(
                config=config,
                controller=_FakeController(),
                vector_store=store,
            )

            stdout = io.StringIO()
            with patch("backend.rag.indexer.bootstrap_core", return_value=fake_core):
                with redirect_stdout(stdout):
                    exit_code = main(["index", str(document_path)])

            self.assertEqual(exit_code, 0)
            self.assertTrue(fake_core.shutdown_called)
            output_payload = json.loads(stdout.getvalue())
            self.assertEqual(output_payload["status"], "indexed")
            self.assertGreater(output_payload["result"]["vector_count"], 0)


if __name__ == "__main__":
    unittest.main()
