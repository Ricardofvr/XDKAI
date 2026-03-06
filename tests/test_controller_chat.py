import logging
import unittest

from backend.config import load_config
from backend.controller import ControllerRequestError, ControllerService
from backend.runtime import ChatGenerationRequest, ChatMessage, ModelInfo, PlaceholderRuntime, RuntimeManager
from backend.runtime.interfaces import (
    EmbeddingGenerationRequest,
    EmbeddingGenerationResponse,
    RuntimeInvocationError,
    RuntimeStatus,
)


class ControllerChatTests(unittest.TestCase):
    def _build_controller(self) -> tuple[ControllerService, str]:
        config = load_config()
        runtime = RuntimeManager(
            primary_backend=PlaceholderRuntime(config.runtime),
            fallback_backend=None,
            selected_provider="placeholder",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
        runtime.startup()

        enabled_models = [
            model.public_name for model in config.runtime.models if model.enabled and model.role in {"general", "coder"}
        ]
        default_model = config.runtime.default_model or enabled_models[0]

        return (
            ControllerService(
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
            ),
            default_model,
        )

    def test_chat_completion_response_shape(self) -> None:
        controller, model_name = self._build_controller()

        request = ChatGenerationRequest(
            model=model_name,
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_123",
        )

        response = controller.create_chat_completion(request)

        self.assertIn("id", response)
        self.assertEqual(response["object"], "chat.completion")
        self.assertEqual(response["model"], model_name)
        self.assertEqual(response["choices"][0]["message"]["role"], "assistant")
        self.assertEqual(response["choices"][0]["finish_reason"], "stop")

    def test_chat_completion_rejects_unknown_model(self) -> None:
        controller, _ = self._build_controller()

        request = ChatGenerationRequest(
            model="unknown-model",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_123",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "model_not_found")

    def test_chat_completion_rejects_disabled_model(self) -> None:
        controller, _ = self._build_controller()

        request = ChatGenerationRequest(
            model="local-coder",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_123",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "model_not_found")

    def test_chat_completion_rejects_embedding_model(self) -> None:
        controller, _ = self._build_controller()

        request = ChatGenerationRequest(
            model="local-embedding",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_123",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "model_not_found")

    def test_list_models_returns_openai_style_list(self) -> None:
        controller, model_name = self._build_controller()
        response = controller.list_models()

        self.assertEqual(response["object"], "list")
        self.assertTrue(response["data"])
        self.assertEqual(response["data"][0]["id"], model_name)

    def test_chat_completion_rejects_stream_mode_for_now(self) -> None:
        controller, model_name = self._build_controller()

        request = ChatGenerationRequest(
            model=model_name,
            messages=[ChatMessage(role="user", content="hello")],
            stream=True,
            request_id="req_123",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "unsupported_feature")

    def test_controller_propagates_runtime_invocation_errors(self) -> None:
        config = load_config()

        class _FailingBackend:
            def startup(self) -> None:
                return

            def shutdown(self) -> None:
                return

            def get_status(self) -> RuntimeStatus:
                return RuntimeStatus(
                    state="ready",
                    provider="local_openai",
                    mode="provider",
                    initialized=True,
                    ready=True,
                    generation_ready=True,
                    embedding_ready=True,
                    provider_reachable=True,
                    active_model="local-general",
                    models_available=["local-general", "local-embedding"],
                    details={},
                )

            def list_models(self) -> list[ModelInfo]:
                return [
                    ModelInfo(id="local-general", role="general", provider_model_id="llama3.2-general"),
                    ModelInfo(id="local-embedding", role="embedding", provider_model_id="nomic-embed-text"),
                ]

            def list_configured_models(self) -> list[ModelInfo]:
                return self.list_models()

            def get_metadata(self) -> dict:
                return {"provider": "local_openai"}

            def generate_chat(self, request: ChatGenerationRequest):
                raise RuntimeInvocationError("mock provider malformed response")

            def stream_chat(self, request: ChatGenerationRequest):
                raise NotImplementedError

            def generate_embeddings(self, request: EmbeddingGenerationRequest) -> EmbeddingGenerationResponse:
                raise RuntimeInvocationError("mock embeddings failure")

        runtime_manager = RuntimeManager(
            primary_backend=_FailingBackend(),
            fallback_backend=None,
            selected_provider="local_openai",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
        runtime_manager.startup()

        controller = ControllerService(
            config=config,
            runtime_manager=runtime_manager,
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
            model="local-general",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_runtime_invocation",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_chat_completion(request)

        self.assertEqual(err.exception.error_type, "runtime_invocation_error")
        self.assertEqual(err.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
