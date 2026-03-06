import logging
import tempfile
import unittest

from backend.config import load_config
from backend.controller import ControllerService
from backend.rag.vector_store import SQLiteVectorStore
from backend.runtime import PlaceholderRuntime, RuntimeManager


class ControllerStatusTests(unittest.TestCase):
    def test_system_status_contains_runtime_and_flags(self) -> None:
        config = load_config()
        runtime = RuntimeManager(
            primary_backend=PlaceholderRuntime(config.runtime),
            fallback_backend=None,
            selected_provider="placeholder",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
        runtime.startup()

        controller = ControllerService(
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
        )

        status = controller.get_system_status()
        self.assertTrue(status["offline_mode"])
        self.assertIn("runtime", status)
        self.assertIn("feature_flags", status)
        self.assertIn("model_registry", status)
        self.assertIn("rag_index", status)
        self.assertIn("rag_chat", status)
        self.assertIn("chat_orchestration", status)
        self.assertEqual(status["runtime"]["provider"], "placeholder")
        self.assertIn("generation", status["runtime"])
        self.assertIn("embeddings", status["runtime"])
        self.assertIn("max_context_characters", status["rag_chat"])
        self.assertIn("deduplicate_results", status["rag_chat"])
        self.assertIn("min_similarity", status["rag_chat"])
        self.assertIn("sessions", status["chat_orchestration"])

    def test_system_status_includes_rag_index_payload(self) -> None:
        config = load_config()
        runtime = RuntimeManager(
            primary_backend=PlaceholderRuntime(config.runtime),
            fallback_backend=None,
            selected_provider="placeholder",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
        runtime.startup()

        with tempfile.TemporaryDirectory() as tmpdir:
            vector_store = SQLiteVectorStore(index_directory=tmpdir)
            vector_store.initialize()

            controller = ControllerService(
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

            status = controller.get_system_status()
            rag_index = status["rag_index"]
            self.assertTrue(rag_index["enabled"])
            self.assertTrue(rag_index["initialized"])
            self.assertIn("documents_indexed", rag_index)
            self.assertIn("total_vectors", rag_index)
            self.assertIn("search_enabled", rag_index)
            self.assertIn("retrieval", rag_index)
            rag_chat = status["rag_chat"]
            self.assertIn("enabled", rag_chat)
            self.assertIn("retrieval_enabled", rag_chat)


if __name__ == "__main__":
    unittest.main()
