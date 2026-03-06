import unittest

from backend.rag.context_builder import build_context_text, inject_context_before_latest_user
from backend.rag.retrieval import RetrievalHit
from backend.runtime.interfaces import ChatMessage


class ContextBuilderTests(unittest.TestCase):
    def test_build_context_text_with_source_metadata(self) -> None:
        hits = [
            RetrievalHit(
                rank=1,
                similarity=0.91,
                document_id="doc1",
                source_file="/tmp/sample.txt",
                chunk_index=0,
                chunk_text="System architecture uses controller orchestration.",
                chunk_preview="System architecture uses controller orchestration.",
                text_length=49,
                metadata={"document_id": "doc1", "chunk_index": 0},
            )
        ]

        text = build_context_text(
            hits=hits,
            context_prefix="Use the context below.",
            include_source_metadata=True,
        )

        self.assertIn("Use the context below.", text)
        self.assertIn("source: /tmp/sample.txt", text)
        self.assertIn("similarity: 0.9100", text)
        self.assertIn("System architecture uses controller orchestration.", text)

    def test_inject_context_before_latest_user(self) -> None:
        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="first question"),
            ChatMessage(role="assistant", content="first answer"),
            ChatMessage(role="user", content="second question"),
        ]

        output = inject_context_before_latest_user(messages, "RAG context message")

        self.assertEqual(len(output), len(messages) + 1)
        self.assertEqual(output[-1].role, "user")
        self.assertEqual(output[-1].content, "second question")
        self.assertEqual(output[-2].role, "system")
        self.assertIn("RAG context message", output[-2].content)


if __name__ == "__main__":
    unittest.main()
