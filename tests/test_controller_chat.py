import logging
import unittest

from backend.config import load_config
from backend.controller import ControllerRequestError, ControllerService
from backend.runtime import ChatGenerationRequest, ChatMessage, PlaceholderRuntime, RuntimeManager


class ControllerChatTests(unittest.TestCase):
    def _build_controller(self) -> ControllerService:
        config = load_config()
        runtime = RuntimeManager(PlaceholderRuntime(config.runtime), logging.getLogger("test.runtime"))
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
        )

    def test_chat_completion_response_shape(self) -> None:
        controller = self._build_controller()

        request = ChatGenerationRequest(
            model="padp-placeholder-chat-001",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_123",
        )

        response = controller.create_chat_completion(request)

        self.assertIn("id", response)
        self.assertEqual(response["object"], "chat.completion")
        self.assertEqual(response["model"], "padp-placeholder-chat-001")
        self.assertEqual(response["choices"][0]["message"]["role"], "assistant")
        self.assertEqual(response["choices"][0]["finish_reason"], "stop")

    def test_chat_completion_rejects_unknown_model(self) -> None:
        controller = self._build_controller()

        request = ChatGenerationRequest(
            model="unknown-model",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_123",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "model_not_found")

    def test_list_models_returns_openai_style_list(self) -> None:
        controller = self._build_controller()
        response = controller.list_models()

        self.assertEqual(response["object"], "list")
        self.assertTrue(response["data"])
        self.assertEqual(response["data"][0]["id"], "padp-placeholder-chat-001")

    def test_chat_completion_rejects_stream_mode_for_now(self) -> None:
        controller = self._build_controller()

        request = ChatGenerationRequest(
            model="padp-placeholder-chat-001",
            messages=[ChatMessage(role="user", content="hello")],
            stream=True,
            request_id="req_123",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "unsupported_feature")


if __name__ == "__main__":
    unittest.main()
