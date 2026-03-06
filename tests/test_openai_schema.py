import unittest

from backend.api.errors import ApiValidationError
from backend.api.openai_schema import (
    parse_chat_completions_request,
    parse_embeddings_request,
    parse_retrieval_search_request,
)


class OpenAISchemaTests(unittest.TestCase):
    def test_parse_chat_request_valid(self) -> None:
        payload = {
            "model": "local-general",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "hello"},
            ],
            "temperature": 0.3,
            "max_tokens": 128,
            "stream": False,
        }

        request = parse_chat_completions_request(payload, request_id="req_test")

        self.assertEqual(request.model, "local-general")
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
            "model": "local-general",
            "messages": "not-an-array",
        }

        with self.assertRaises(ApiValidationError):
            parse_chat_completions_request(payload, request_id="req_test")

    def test_parse_embeddings_single_input(self) -> None:
        payload = {
            "model": "local-embedding",
            "input": "hello embeddings",
            "encoding_format": "float",
        }

        request = parse_embeddings_request(payload, request_id="req_embed")
        self.assertEqual(request.model, "local-embedding")
        self.assertEqual(request.input_texts, ["hello embeddings"])
        self.assertEqual(request.encoding_format, "float")

    def test_parse_embeddings_batch_input(self) -> None:
        payload = {
            "model": "local-embedding",
            "input": ["one", "two"],
        }

        request = parse_embeddings_request(payload, request_id="req_embed")
        self.assertEqual(request.input_texts, ["one", "two"])

    def test_parse_embeddings_invalid_input(self) -> None:
        payload = {
            "model": "local-embedding",
            "input": ["one", ""],
        }

        with self.assertRaises(ApiValidationError):
            parse_embeddings_request(payload, request_id="req_embed")

    def test_parse_retrieval_search_request_valid(self) -> None:
        payload = {
            "query": "architecture",
            "top_k": 5,
            "embedding_model": "local-embedding",
            "min_similarity": -0.5,
        }
        request = parse_retrieval_search_request(payload, request_id="req_ret")
        self.assertEqual(request.query, "architecture")
        self.assertEqual(request.top_k, 5)
        self.assertEqual(request.embedding_model, "local-embedding")
        self.assertEqual(request.min_similarity, -0.5)

    def test_parse_retrieval_search_request_invalid_query(self) -> None:
        with self.assertRaises(ApiValidationError):
            parse_retrieval_search_request({"query": ""}, request_id="req_ret")


if __name__ == "__main__":
    unittest.main()
