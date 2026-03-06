import io
import json
import logging
import unittest
from unittest.mock import patch
from urllib import error

from backend.config import load_config
from backend.runtime.interfaces import ChatGenerationRequest, ChatMessage, RuntimeInvocationError, RuntimeUnavailableError
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

    def test_model_resolution_uses_provider_model_id(self) -> None:
        runtime = self._build_runtime()
        captured_model = {"value": None}

        def fake_urlopen(req, timeout=0):
            if req.full_url.endswith("/health"):
                return _MockHTTPResponse()
            if req.full_url.endswith("/v1/models"):
                return _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}]})
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

    def test_chat_timeout_raises_runtime_unavailable(self) -> None:
        runtime = self._build_runtime()

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}]}),
                TimeoutError("timed out"),
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeUnavailableError):
                runtime.generate_chat(self._chat_request())

    def test_malformed_chat_response_raises_runtime_invocation_error(self) -> None:
        runtime = self._build_runtime()

        with patch(
            "backend.runtime.providers.local_openai.request.urlopen",
            side_effect=[
                _MockHTTPResponse(),
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}]}),
                _MockHTTPResponse(payload={"choices": "invalid"}),
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeInvocationError):
                runtime.generate_chat(self._chat_request())

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
                _MockHTTPResponse(payload={"data": [{"id": "llama3.2-general"}]}),
                provider_error,
            ],
        ):
            runtime.startup()
            with self.assertRaises(RuntimeInvocationError) as err:
                runtime.generate_chat(self._chat_request())

        self.assertIn("Model not loaded", str(err.exception))


if __name__ == "__main__":
    unittest.main()
