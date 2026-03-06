import unittest

from backend.rag.retrieval import RetrievalHit
from backend.rag.retrieval_postprocessing import (
    RetrievalPostprocessConfig,
    postprocess_retrieval_hits,
)


def _hit(
    *,
    rank: int,
    similarity: float,
    document_id: str,
    source_file: str,
    chunk_index: int,
    text: str,
) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        similarity=similarity,
        document_id=document_id,
        source_file=source_file,
        chunk_index=chunk_index,
        chunk_text=text,
        chunk_preview=text,
        text_length=len(text),
        metadata={"document_id": document_id, "chunk_index": chunk_index, "text_length": len(text)},
    )


class RetrievalPostprocessingTests(unittest.TestCase):
    def test_filters_exact_and_near_duplicates(self) -> None:
        hits = [
            _hit(
                rank=1,
                similarity=0.91,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=0,
                text="Controller orchestrates retrieval and generation.",
            ),
            _hit(
                rank=2,
                similarity=0.9,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=1,
                text="Controller orchestrates retrieval and generation.",
            ),
            _hit(
                rank=3,
                similarity=0.89,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=2,
                text="Controller orchestrates retrieval + generation.",
            ),
        ]
        result = postprocess_retrieval_hits(
            hits,
            RetrievalPostprocessConfig(
                min_similarity=0.0,
                deduplicate_results=True,
                near_duplicate_threshold=0.9,
                max_chunks_per_document=3,
                max_context_chunks=3,
                max_context_characters=4000,
            ),
        )

        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.diagnostics.duplicate_filtered_count, 1)
        self.assertEqual(result.diagnostics.near_duplicate_filtered_count, 1)

    def test_limits_chunks_per_document(self) -> None:
        hits = [
            _hit(
                rank=1,
                similarity=0.95,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=0,
                text="chunk-0",
            ),
            _hit(
                rank=2,
                similarity=0.94,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=1,
                text="chunk-1",
            ),
            _hit(
                rank=3,
                similarity=0.93,
                document_id="doc2",
                source_file="/tmp/b.txt",
                chunk_index=0,
                text="chunk-b",
            ),
        ]
        result = postprocess_retrieval_hits(
            hits,
            RetrievalPostprocessConfig(
                min_similarity=0.0,
                deduplicate_results=False,
                near_duplicate_threshold=0.92,
                max_chunks_per_document=1,
                max_context_chunks=3,
                max_context_characters=4000,
            ),
        )

        self.assertEqual([item.document_id for item in result.hits], ["doc1", "doc2"])
        self.assertEqual(result.diagnostics.per_document_filtered_count, 1)

    def test_enforces_character_budget_with_truncation(self) -> None:
        first_text = "A" * 120
        second_text = "B" * 120
        hits = [
            _hit(
                rank=1,
                similarity=0.93,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=0,
                text=first_text,
            ),
            _hit(
                rank=2,
                similarity=0.9,
                document_id="doc2",
                source_file="/tmp/b.txt",
                chunk_index=0,
                text=second_text,
            ),
        ]
        result = postprocess_retrieval_hits(
            hits,
            RetrievalPostprocessConfig(
                min_similarity=0.0,
                deduplicate_results=False,
                near_duplicate_threshold=0.92,
                max_chunks_per_document=2,
                max_context_chunks=3,
                max_context_characters=210,
            ),
        )

        self.assertEqual(len(result.hits), 2)
        self.assertTrue(result.hits[1].metadata.get("truncated"))
        self.assertLessEqual(sum(len(item.chunk_text) for item in result.hits), 210)
        self.assertEqual(result.diagnostics.budget_truncated_count, 1)
        self.assertTrue(result.diagnostics.budget_character_limit_applied)

    def test_min_similarity_filtering(self) -> None:
        hits = [
            _hit(
                rank=1,
                similarity=0.7,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=0,
                text="relevant",
            ),
            _hit(
                rank=2,
                similarity=0.05,
                document_id="doc2",
                source_file="/tmp/b.txt",
                chunk_index=0,
                text="low similarity",
            ),
        ]
        result = postprocess_retrieval_hits(
            hits,
            RetrievalPostprocessConfig(
                min_similarity=0.1,
                deduplicate_results=False,
                near_duplicate_threshold=0.92,
                max_chunks_per_document=2,
                max_context_chunks=3,
                max_context_characters=4000,
            ),
        )

        self.assertEqual(len(result.hits), 1)
        self.assertEqual(result.hits[0].document_id, "doc1")
        self.assertEqual(result.diagnostics.similarity_filtered_count, 1)

    def test_preserves_rank_order_after_filtering(self) -> None:
        hits = [
            _hit(
                rank=1,
                similarity=0.95,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=0,
                text="high score unique",
            ),
            _hit(
                rank=2,
                similarity=0.93,
                document_id="doc1",
                source_file="/tmp/a.txt",
                chunk_index=1,
                text="high score unique",
            ),
            _hit(
                rank=3,
                similarity=0.9,
                document_id="doc2",
                source_file="/tmp/b.txt",
                chunk_index=0,
                text="second document kept",
            ),
        ]
        result = postprocess_retrieval_hits(
            hits,
            RetrievalPostprocessConfig(
                min_similarity=0.0,
                deduplicate_results=True,
                near_duplicate_threshold=0.9,
                max_chunks_per_document=3,
                max_context_chunks=3,
                max_context_characters=4000,
            ),
        )

        self.assertEqual([hit.rank for hit in result.hits], [1, 3])


if __name__ == "__main__":
    unittest.main()
