import type { SystemStatus } from "../types";

type Props = {
  status: SystemStatus | null;
};

export function DiagnosticsPanel({ status }: Props) {
  const diagnostics: string[] = [];
  const runtime = status?.runtime;
  const ragIndex = status?.rag_index;
  const ragChat = status?.rag_chat;

  if (!status) {
    diagnostics.push("No backend status available.");
  }
  if (runtime?.fallback_engaged) {
    diagnostics.push("Provider fallback is active.");
  }
  if (runtime?.state && runtime.state !== "ready") {
    diagnostics.push(`Runtime state is ${runtime.state}.`);
  }
  if (runtime && runtime.generation_ready === false) {
    diagnostics.push("Generation is not ready.");
  }
  if (runtime && runtime.embedding_ready === false) {
    diagnostics.push("Embeddings are not ready.");
  }
  if ((ragIndex?.total_vectors ?? 0) === 0) {
    diagnostics.push("RAG index is empty. Run indexing before retrieval/chat context tests.");
  }
  if (ragIndex?.search_enabled === false) {
    diagnostics.push("Retrieval is currently unavailable.");
  }
  const lastRetrieval = ragChat?.last_retrieval_diagnostics;
  if (lastRetrieval && typeof lastRetrieval === "object") {
    const inputCount = Number(lastRetrieval["input_count"] ?? 0);
    const outputCount = Number(lastRetrieval["output_count"] ?? 0);
    if (inputCount > 0 && outputCount === 0) {
      diagnostics.push("Retrieval results were filtered out by current quality thresholds.");
    }
    if (Boolean(lastRetrieval["budget_character_limit_applied"])) {
      diagnostics.push("Context character budget was applied on the last retrieval.");
    }
  }

  return (
    <section className="panel">
      <h2>Diagnostics</h2>
      <ul className="diagnostics-list">
        {(diagnostics.length ? diagnostics : ["No major diagnostics detected."]).map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
