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

    def test_load_config_from_explicit_path(self) -> None:
        config = load_config(Path("config/portable-ai-drive-pro.json"))
        self.assertEqual(config.runtime.provider, "local_openai")
        self.assertGreaterEqual(len(config.runtime.models), 1)

    def test_model_registry_fields_are_loaded(self) -> None:
        config = load_config()
        first_model = config.runtime.models[0]

        self.assertTrue(first_model.public_name)
        self.assertTrue(first_model.provider_model_id)
        self.assertIn(first_model.role, {"general", "coder"})
        self.assertIsInstance(first_model.enabled, bool)


if __name__ == "__main__":
    unittest.main()
