import unittest

from backend.rag.chunking import chunk_text


class RagChunkingTests(unittest.TestCase):
    def test_chunk_text_returns_deterministic_chunks(self) -> None:
        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = chunk_text(document_id="doc1", text=text, chunk_size=10, chunk_overlap=2)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].text, "abcdefghij")
        self.assertEqual(chunks[1].text, "ijklmnopqr")
        self.assertEqual(chunks[2].text, "qrstuvwxyz")

    def test_chunk_overlap_is_applied(self) -> None:
        text = "0123456789"
        chunks = chunk_text(document_id="doc2", text=text, chunk_size=4, chunk_overlap=1)

        self.assertEqual([chunk.text for chunk in chunks], ["0123", "3456", "6789"])
        self.assertEqual([chunk.text_length for chunk in chunks], [4, 4, 4])

    def test_chunk_text_validates_inputs(self) -> None:
        with self.assertRaises(ValueError):
            chunk_text(document_id="", text="abc", chunk_size=5, chunk_overlap=1)

        with self.assertRaises(ValueError):
            chunk_text(document_id="doc", text="abc", chunk_size=0, chunk_overlap=0)

        with self.assertRaises(ValueError):
            chunk_text(document_id="doc", text="abc", chunk_size=5, chunk_overlap=5)


if __name__ == "__main__":
    unittest.main()
