import type { RagIndexStatus } from "../types";

type Props = {
  ragIndex: RagIndexStatus | undefined;
};

export function RagIndexPanel({ ragIndex }: Props) {
  return (
    <section className="panel">
      <h2>RAG Index Overview</h2>
      <div className="status-grid">
        <div className="status-item">
          <span>Initialized</span>
          <strong>{String(ragIndex?.initialized ?? false)}</strong>
        </div>
        <div className="status-item">
          <span>Total Documents</span>
          <strong>{ragIndex?.total_documents ?? ragIndex?.documents_indexed ?? 0}</strong>
        </div>
        <div className="status-item">
          <span>Total Vectors</span>
          <strong>{ragIndex?.total_vectors ?? 0}</strong>
        </div>
        <div className="status-item">
          <span>Embedding Model</span>
          <strong>{ragIndex?.embedding_model ?? "-"}</strong>
        </div>
        <div className="status-item">
          <span>Last Indexed</span>
          <strong>{ragIndex?.last_indexed_at ?? "-"}</strong>
        </div>
        <div className="status-item">
          <span>Retrieval Enabled</span>
          <strong>{String(ragIndex?.search_enabled ?? false)}</strong>
        </div>
      </div>
      <p className="mono small">{ragIndex?.index_location}</p>
    </section>
  );
}
