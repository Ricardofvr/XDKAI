from pathlib import Path
import unittest

from backend.config import load_config


class ConfigLoaderTests(unittest.TestCase):
    def test_load_default_config(self) -> None:
        config = load_config()
        self.assertEqual(config.app.name, "Portable AI Drive PRO")
        self.assertEqual(config.api.host, "127.0.0.1")
        self.assertTrue(config.operating_mode.offline_default)

    def test_load_config_from_explicit_path(self) -> None:
        config = load_config(Path("config/portable-ai-drive-pro.json"))
        self.assertEqual(config.runtime.provider, "placeholder")


if __name__ == "__main__":
    unittest.main()
