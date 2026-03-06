from pathlib import Path
import unittest

from backend.config import load_config


class ConfigLoaderTests(unittest.TestCase):
    def test_load_default_config(self) -> None:
        config = load_config()
        self.assertEqual(config.app.name, "Portable AI Drive PRO")
        self.assertEqual(config.api.host, "127.0.0.1")
        self.assertTrue(config.operating_mode.offline_default)
        self.assertEqual(config.runtime.provider, "local_openai")
        self.assertTrue(config.runtime.allow_fallback_to_placeholder)
        self.assertEqual(config.runtime.default_embedding_model, "local-embedding")
        self.assertTrue(config.rag.enabled)
        self.assertEqual(config.rag.default_embedding_model, "local-embedding")
        self.assertTrue(config.rag.chat.enabled)
        self.assertGreater(config.rag.chat.max_context_chunks, 0)

    def test_load_config_from_explicit_path(self) -> None:
        config = load_config(Path("config/portable-ai-drive-pro.json"))
        self.assertEqual(config.runtime.provider, "local_openai")
        self.assertGreaterEqual(len(config.runtime.models), 1)

    def test_model_registry_fields_are_loaded(self) -> None:
        config = load_config()
        first_model = config.runtime.models[0]

        self.assertTrue(first_model.public_name)
        self.assertTrue(first_model.provider_model_id)
        self.assertIn(first_model.role, {"general", "coder", "embedding"})
        self.assertIsInstance(first_model.enabled, bool)

    def test_rag_chunking_and_index_settings_are_loaded(self) -> None:
        config = load_config()
        self.assertGreater(config.rag.chunking.chunk_size, 0)
        self.assertGreaterEqual(config.rag.chunking.chunk_overlap, 0)
        self.assertTrue(config.rag.index.directory)
        self.assertTrue(config.rag.index.vectors_db_filename.endswith(".db"))
        self.assertGreater(config.rag.retrieval.top_k, 0)
        self.assertEqual(config.rag.retrieval.similarity_metric, "cosine")
        self.assertTrue(config.rag.chat.context_prefix)


if __name__ == "__main__":
    unittest.main()
