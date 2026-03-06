import { useState } from "react";

import { searchRetrieval } from "../lib/api";
import type { RetrievalResponse } from "../types";

type Props = {
  defaultTopK?: number;
};

export function RetrievalTestPanel({ defaultTopK = 3 }: Props) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState<number>(defaultTopK);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<RetrievalResponse | null>(null);

  async function onSearch() {
    if (!query.trim() || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const response = await searchRetrieval({ query: query.trim(), topK });
      setResults(response);
    } catch (err) {
      setError((err as Error).message || "Retrieval failed");
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel panel-wide">
      <h2>Retrieval Test</h2>
      <div className="retrieval-controls">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ask retrieval query"
        />
        <label>
          Top K
          <input
            type="number"
            min={1}
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value) || 1)}
          />
        </label>
        <button onClick={onSearch} disabled={!query.trim() || loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </div>
      {error ? <p className="error-text">{error}</p> : null}

      <div className="retrieval-results">
        {(results?.results ?? []).map((result) => (
          <div className="retrieval-entry" key={`${result.document_id}-${result.chunk_index}`}>
            <div className="retrieval-meta">
              <span>#{result.rank}</span>
              <span>similarity: {result.similarity.toFixed(4)}</span>
              <span className="mono">{result.source_file}</span>
              <span>chunk: {result.chunk_index}</span>
            </div>
            <p>{result.chunk_preview || result.chunk_text}</p>
          </div>
        ))}
        {results && results.result_count === 0 ? <p>No retrieval matches.</p> : null}
      </div>
    </section>
  );
}
