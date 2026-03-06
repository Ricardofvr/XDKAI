import logging
import unittest

from backend.config import load_config
from backend.controller import ControllerRequestError, ControllerService
from backend.runtime import (
    EmbeddingGenerationRequest,
    EmbeddingGenerationResponse,
    EmbeddingVector,
    ModelInfo,
    PlaceholderRuntime,
    RuntimeManager,
)
from backend.runtime.interfaces import RuntimeInvocationError, RuntimeStatus, RuntimeUnavailableError


class ControllerEmbeddingsTests(unittest.TestCase):
    def _build_controller(self) -> ControllerService:
        config = load_config()
        runtime = RuntimeManager(
            primary_backend=PlaceholderRuntime(config.runtime),
            fallback_backend=None,
            selected_provider="placeholder",
            fallback_provider=None,
            logger=logging.getLogger("test.runtime"),
        )
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

    def test_embeddings_response_shape_single_input(self) -> None:
        controller = self._build_controller()

        request = EmbeddingGenerationRequest(
            model="local-embedding",
            input_texts=["hello"],
            request_id="req_embed_1",
        )

        response = controller.create_embeddings(request)
        self.assertEqual(response["object"], "list")
        self.assertEqual(response["model"], "local-embedding")
        self.assertEqual(len(response["data"]), 1)
        self.assertEqual(response["data"][0]["object"], "embedding")
        self.assertIsInstance(response["data"][0]["embedding"], list)

    def test_embeddings_response_shape_batch_input(self) -> None:
        controller = self._build_controller()

        request = EmbeddingGenerationRequest(
            model="local-embedding",
            input_texts=["one", "two", "three"],
            request_id="req_embed_2",
        )

        response = controller.create_embeddings(request)
        self.assertEqual(len(response["data"]), 3)

    def test_embeddings_rejects_non_embedding_model(self) -> None:
        controller = self._build_controller()

        request = EmbeddingGenerationRequest(
            model="local-general",
            input_texts=["hello"],
            request_id="req_embed_3",
        )

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_embeddings(request)

        self.assertEqual(err.exception.error_type, "model_not_found")

    def test_embeddings_propagates_runtime_unavailable(self) -> None:
        config = load_config()

        class _UnavailableEmbeddingBackend:
            def startup(self) -> None:
                return

            def shutdown(self) -> None:
                return

            def get_status(self) -> RuntimeStatus:
                return RuntimeStatus(
                    state="degraded",
                    provider="local_openai",
                    mode="provider",
                    initialized=True,
                    ready=True,
                    generation_ready=True,
                    embedding_ready=False,
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

            def generate_chat(self, request):
                raise RuntimeUnavailableError("chat unavailable")

            def stream_chat(self, request):
                raise NotImplementedError

            def generate_embeddings(self, request):
                raise RuntimeUnavailableError("embedding unavailable")

        runtime_manager = RuntimeManager(
            primary_backend=_UnavailableEmbeddingBackend(),
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

        request = EmbeddingGenerationRequest(model="local-embedding", input_texts=["hello"], request_id="req_embed_4")

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_embeddings(request)

        self.assertEqual(err.exception.error_type, "runtime_unavailable")
        self.assertEqual(err.exception.status_code, 503)

    def test_embeddings_propagates_runtime_invocation_error(self) -> None:
        config = load_config()

        class _FailingEmbeddingBackend:
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

            def generate_chat(self, request):
                raise RuntimeInvocationError("chat failure")

            def stream_chat(self, request):
                raise NotImplementedError

            def generate_embeddings(self, request):
                raise RuntimeInvocationError("embedding malformed payload")

        runtime_manager = RuntimeManager(
            primary_backend=_FailingEmbeddingBackend(),
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

        request = EmbeddingGenerationRequest(model="local-embedding", input_texts=["hello"], request_id="req_embed_5")

        with self.assertRaises(ControllerRequestError) as err:
            controller.create_embeddings(request)

        self.assertEqual(err.exception.error_type, "runtime_invocation_error")
        self.assertEqual(err.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
