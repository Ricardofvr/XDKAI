import type { SystemStatus } from "../types";

type Props = {
  status: SystemStatus | null;
  loading: boolean;
};

function item(label: string, value: string | number | boolean | null | undefined) {
  return (
    <div className="status-item" key={label}>
      <span>{label}</span>
      <strong>{value === undefined || value === null ? "-" : String(value)}</strong>
    </div>
  );
}

export function SystemOverviewPanel({ status, loading }: Props) {
  const runtime = status?.runtime;
  const sessions = status?.chat_orchestration?.sessions;
  const summarisation = status?.chat_orchestration?.summarisation;

  return (
    <section className="panel panel-wide">
      <h2>System Overview</h2>
      {loading && !status ? <p>Loading status...</p> : null}
      <div className="status-grid">
        {item("Environment", status?.environment)}
        {item("Offline Mode", status?.offline_mode)}
        {item("Runtime State", runtime?.state)}
        {item("Selected Provider", runtime?.selected_provider)}
        {item("Active Provider", runtime?.active_provider || runtime?.provider)}
        {item("Fallback Engaged", runtime?.fallback_engaged)}
        {item("Generation Ready", runtime?.generation_ready)}
        {item("Embeddings Ready", runtime?.embedding_ready)}
        {item("Active Model", runtime?.active_model)}
        {item("Runtime Mode", runtime?.mode)}
        {item("Session Store", sessions?.storage_mode)}
        {item("Sessions In Memory", sessions?.sessions_in_memory)}
        {item("Summarisation Enabled", summarisation?.enabled)}
        {item("Compaction Recommended", summarisation?.last_compaction_assessment?.recommended)}
      </div>
    </section>
  );
}
