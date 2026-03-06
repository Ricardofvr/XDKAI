import json
import logging
import tempfile
import unittest
from pathlib import Path

from backend.config import load_config
from backend.controller import ControllerRequestError, ControllerService
from backend.runtime import ChatGenerationRequest, ChatMessage, RuntimeManager, build_runtime_backends
from backend.runtime.providers import LocalOpenAIRuntime


def _load_config_with_mutation(mutation_fn) -> object:
    base_config_path = Path("config/portable-ai-drive-pro.json")
    data = json.loads(base_config_path.read_text(encoding="utf-8"))
    mutation_fn(data)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        tmp.write(json.dumps(data))
        tmp_path = Path(tmp.name)

    try:
        return load_config(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


class RuntimeSelectionTests(unittest.TestCase):
    def test_provider_selection_builds_local_runtime_and_placeholder_fallback(self) -> None:
        config = load_config()
        primary, fallback = build_runtime_backends(config.runtime, logging.getLogger("test.runtime.providers"))

        self.assertIsInstance(primary, LocalOpenAIRuntime)
        self.assertIsNotNone(fallback)

    def test_fallback_engages_when_local_runtime_unavailable(self) -> None:
        config = _load_config_with_mutation(
            lambda data: data["runtime"]["local_openai"].update({"base_url": "http://127.0.0.1:65530"})
        )
        primary, fallback = build_runtime_backends(config.runtime, logging.getLogger("test.runtime.providers"))

        manager = RuntimeManager(
            primary_backend=primary,
            fallback_backend=fallback,
            selected_provider=config.runtime.provider,
            fallback_provider=config.runtime.fallback_provider,
            logger=logging.getLogger("test.runtime.manager"),
        )
        manager.startup()

        status = manager.get_status_payload()
        self.assertTrue(status["fallback_engaged"])
        self.assertEqual(status["selected_provider"], "local_openai")
        self.assertEqual(status["active_provider"], "placeholder")
        self.assertTrue(status["ready"])

    def test_degraded_state_without_fallback(self) -> None:
        def mutate(data: dict) -> None:
            data["runtime"]["allow_fallback_to_placeholder"] = False
            data["runtime"]["fallback_provider"] = None
            data["runtime"]["local_openai"]["base_url"] = "http://127.0.0.1:65531"

        config = _load_config_with_mutation(mutate)
        primary, fallback = build_runtime_backends(config.runtime, logging.getLogger("test.runtime.providers"))
        self.assertIsNone(fallback)

        manager = RuntimeManager(
            primary_backend=primary,
            fallback_backend=fallback,
            selected_provider=config.runtime.provider,
            fallback_provider=config.runtime.fallback_provider,
            logger=logging.getLogger("test.runtime.manager"),
        )
        manager.startup()

        status = manager.get_status_payload()
        self.assertFalse(status["ready"])
        self.assertEqual(status["active_provider"], "local_openai")
        self.assertEqual(status["state"], "degraded")

    def test_controller_reports_runtime_unavailable_when_degraded(self) -> None:
        def mutate(data: dict) -> None:
            data["runtime"]["allow_fallback_to_placeholder"] = False
            data["runtime"]["fallback_provider"] = None
            data["runtime"]["local_openai"]["base_url"] = "http://127.0.0.1:65532"

        config = _load_config_with_mutation(mutate)
        primary, fallback = build_runtime_backends(config.runtime, logging.getLogger("test.runtime.providers"))
        manager = RuntimeManager(
            primary_backend=primary,
            fallback_backend=fallback,
            selected_provider=config.runtime.provider,
            fallback_provider=config.runtime.fallback_provider,
            logger=logging.getLogger("test.runtime.manager"),
        )
        manager.startup()

        controller = ControllerService(
            config=config,
            runtime_manager=manager,
            logger=logging.getLogger("test.controller"),
            startup_state={
                "config_loaded": True,
                "logging_initialized": True,
                "runtime_initialized": True,
                "controller_initialized": True,
                "api_initialized": True,
            },
        )

        request = ChatGenerationRequest(
            model=config.runtime.default_model or "local-general",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_test_runtime_unavailable",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "runtime_unavailable")
        self.assertEqual(err.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
