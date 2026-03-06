import logging
import unittest

from backend.config import load_config
from backend.controller import ControllerService
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
        self.assertEqual(status["runtime"]["provider"], "placeholder")


if __name__ == "__main__":
    unittest.main()
