import io
import json
import logging
import unittest
from unittest.mock import patch
from urllib import error

from backend.config import load_config
from backend.runtime.interfaces import (
    ChatGenerationRequest,
    ChatMessage,
    EmbeddingGenerationRequest,
    RuntimeInvocationError,
    RuntimeUnavailableError,
)
from backend.runtime.providers import LocalOpenAIRuntime


class _MockHTTPResponse:
    def __init__(self, payload: dict | None = None, raw: bytes | None = None) -> None:
        if raw is not None:
            self._raw = raw
        elif payload is None:
            self._raw = b""
        else:
            self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LocalOpenAIRuntimeTests(unittest.TestCase):
    def _build_runtime(self) -> LocalOpenAIRuntime:
        config = load_config()
        return LocalOpenAIRuntime(config.runtime, logging.getLogger("test.runtime.local_openai"))

    def _chat_request(self) -> ChatGenerationRequest:
        return ChatGenerationRequest(
            model="local-general",
            messages=[ChatMessage(role="user", content="hello")],
            stream=False,
            request_id="req_test",
        )

    def _embedding_request(self) -> EmbeddingGenerationRequest:
        return EmbeddingGenerationRequest(
            model="local-embedding",
            input_texts=["hello embeddings"],
            encoding_format="float",
            request_id="req_embed",
        )

    def test_model_resolution_uses_provider_model_id(self) -> None:
        runtime = self._build_runtime()
        captured_model = {"value": None}

        def fake_urlopen(req, timeout=0):
            if req.full_url.endswith("/health"):
                return _MockHTTPResponse()
            if req.full_url.endswith("/v1/models"):
                return _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]})
            if req.full_url.endswith("/v1/chat/completions"):
                body = json.loads(req.data.decode("utf-8"))
                captured_model["value"] = body.get("model")
                return _MockHTTPResponse(
                    payload={
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "real provider output"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
                    }
                )
            raise AssertionError(f"Unexpected URL in test: {req.full_url}")

        with patch("backend.runtime.providers.local_openai.request.urlopen", side_effect=fake_urlopen):
            runtime.startup()
            response = runtime.generate_chat(self._chat_request())

        self.assertEqual(captured_model["value"], "llama3.2-general")
        self.assertEqual(response.choices[0].message.content, "real provider output")
        self.assertEqual(response.usage["total_tokens"], 7)

    def test_embedding_model_resolution_uses_provider_model_id(self) -> None:
        runtime = self._build_runtime()
        captured_model = {"value": None}

        def fake_urlopen(req, timeout=0):
            if req.full_url.endswith("/health"):
                return _MockHTTPResponse()
            if req.full_url.endswith("/v1/models"):
                return _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]})
            if req.full_url.endswith("/v1/embeddings"):
                body = json.loads(req.data.decode("utf-8"))
                captured_model["value"] = body.get("model")
                return _MockHTTPResponse(
                    payload={
                        "object": "list",
                        "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
                        "usage": {"prompt_tokens": 5, "total_tokens": 5},
                    }
                )
            raise AssertionError(f"Unexpected URL in test: {req.full_url}")

        with patch("backend.runtime.providers.local_openai.request.urlopen", side_effect=fake_urlopen):
            runtime.startup()
            response = runtime.generate_embeddings(self._embedding_request())

        self.assertEqual(captured_model["value"], "nomic-embed-text")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].embedding, [0.1, 0.2, 0.3])

    def test_chat_timeout_raises_runtime_unavailable(self) -> None:
        runtime = self._build_runtime()

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]}),
                TimeoutError("timed out"),
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeUnavailableError):
                runtime.generate_chat(self._chat_request())

    def test_embeddings_timeout_raises_runtime_unavailable(self) -> None:
        runtime = self._build_runtime()

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]}),
                TimeoutError("timed out"),
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeUnavailableError):
                runtime.generate_embeddings(self._embedding_request())

    def test_malformed_chat_response_raises_runtime_invocation_error(self) -> None:
        runtime = self._build_runtime()

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]}),
                _MockHTTPResponse(payload={"choices": "invalid"}),
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeInvocationError):
                runtime.generate_chat(self._chat_request())

    def test_malformed_embeddings_response_raises_runtime_invocation_error(self) -> None:
        runtime = self._build_runtime()

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]}),
                _MockHTTPResponse(payload={"data": [{"index": 0, "embedding": "invalid"}]}),
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeInvocationError):
                runtime.generate_embeddings(self._embedding_request())

    def test_provider_error_payload_is_normalized(self) -> None:
        runtime = self._build_runtime()
        provider_error = error.HTTPError(
            url="http://127.0.0.1:8081/v1/chat/completions",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"Model not loaded"}}'),
        )

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]}),
                provider_error,
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeInvocationError) as err:
                runtime.generate_chat(self._chat_request())

        self.assertIn("Model not loaded", str(err.exception))

    def test_provider_error_payload_is_normalized_for_embeddings(self) -> None:
        runtime = self._build_runtime()
        provider_error = error.HTTPError(
            url="http://127.0.0.1:8081/v1/embeddings",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"Embedding model unavailable"}}'),
        )

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}, {"id": "nomic-embed-text"}]}),
                provider_error,
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeInvocationError) as err:
                runtime.generate_embeddings(self._embedding_request())

        self.assertIn("Embedding model unavailable", str(err.exception))


if __name__ == "__main__":
    unittest.main()
