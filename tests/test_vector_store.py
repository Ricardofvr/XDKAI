import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.rag.vector_store import IndexedDocument, SQLiteVectorStore, VectorRecord


class VectorStoreTests(unittest.TestCase):
    def test_vector_store_inserts_and_persists_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteVectorStore(index_directory=tmpdir)
            store.initialize()

            now = datetime.now(timezone.utc).isoformat()
            document = IndexedDocument(
                document_id="doc123",
                source_file="/tmp/doc.txt",
                chunk_count=2,
                embedding_model="local-embedding",
                indexed_at_utc=now,
            )
            vectors = [
                VectorRecord(
                    document_id="doc123",
                    chunk_index=0,
                    embedding=[0.1, 0.2, 0.3],
                    chunk_text="first chunk text",
                    text_length=12,
                    metadata={"document_id": "doc123", "chunk_index": 0, "text_length": 12},
                ),
                VectorRecord(
                    document_id="doc123",
                    chunk_index=1,
                    embedding=[0.4, 0.5, 0.6],
                    chunk_text="second chunk text",
                    text_length=10,
                    metadata={"document_id": "doc123", "chunk_index": 1, "text_length": 10},
                ),
            ]

            store.upsert_document(document, vectors)

            self.assertEqual(store.count_vectors(), 2)
            docs = store.list_indexed_documents()
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0].document_id, "doc123")

            status = store.get_status_payload()
            self.assertTrue(status["initialized"])
            self.assertEqual(status["documents_indexed"], 1)
            self.assertEqual(status["total_vectors"], 2)
            self.assertIn("local-embedding", status["embedding_models"])

            documents_path = Path(tmpdir) / "documents.json"
            metadata_path = Path(tmpdir) / "metadata.json"
            self.assertTrue(documents_path.exists())
            self.assertTrue(metadata_path.exists())

            documents_payload = json.loads(documents_path.read_text(encoding="utf-8"))
            metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8"))

            self.assertEqual(len(documents_payload), 1)
            self.assertEqual(documents_payload[0]["document_id"], "doc123")
            self.assertEqual(metadata_payload["documents_indexed"], 1)
            self.assertEqual(metadata_payload["total_vectors"], 2)

    def test_similarity_search_returns_ranked_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteVectorStore(index_directory=tmpdir)
            store.initialize()

            now = datetime.now(timezone.utc).isoformat()
            document = IndexedDocument(
                document_id="docA",
                source_file="/tmp/docA.txt",
                chunk_count=2,
                embedding_model="local-embedding",
                indexed_at_utc=now,
            )
            vectors = [
                VectorRecord(
                    document_id="docA",
                    chunk_index=0,
                    embedding=[1.0, 0.0, 0.0],
                    chunk_text="architecture overview chunk",
                    text_length=27,
                    metadata={"document_id": "docA", "chunk_index": 0, "text_length": 27},
                ),
                VectorRecord(
                    document_id="docA",
                    chunk_index=1,
                    embedding=[0.0, 1.0, 0.0],
                    chunk_text="unrelated content chunk",
                    text_length=23,
                    metadata={"document_id": "docA", "chunk_index": 1, "text_length": 23},
                ),
            ]
            store.upsert_document(document, vectors)

            results = store.search_similar(
                query_embedding=[0.9, 0.1, 0.0],
                top_k=2,
                min_similarity=0.0,
                similarity_metric="cosine",
            )

            self.assertEqual(len(results), 2)
            self.assertGreater(results[0].similarity, results[1].similarity)
            self.assertEqual(results[0].chunk_index, 0)
            self.assertEqual(results[0].chunk_text, "architecture overview chunk")


if __name__ == "__main__":
    unittest.main()
