import unittest

from backend.api.errors import ApiValidationError
from backend.api.openai_schema import parse_chat_completions_request


class OpenAISchemaTests(unittest.TestCase):
    def test_parse_chat_request_valid(self) -> None:
        payload = {
            "model": "padp-placeholder-chat-001",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "hello"},
            ],
            "temperature": 0.3,
            "max_tokens": 128,
            "stream": False,
        }

        request = parse_chat_completions_request(payload, request_id="req_test")

        self.assertEqual(request.model, "padp-placeholder-chat-001")
        self.assertEqual(len(request.messages), 2)
        self.assertEqual(request.messages[1].role, "user")
        self.assertEqual(request.messages[1].content, "hello")
        self.assertFalse(request.stream)

    def test_parse_chat_request_missing_model(self) -> None:
        payload = {
            "messages": [{"role": "user", "content": "hello"}],
        }

        with self.assertRaises(ApiValidationError):
            parse_chat_completions_request(payload, request_id="req_test")

    def test_parse_chat_request_invalid_messages(self) -> None:
        payload = {
            "model": "padp-placeholder-chat-001",
            "messages": "not-an-array",
        }

        with self.assertRaises(ApiValidationError):
            parse_chat_completions_request(payload, request_id="req_test")


if __name__ == "__main__":
    unittest.main()
