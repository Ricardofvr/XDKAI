import type { ModelsResponse, SystemStatus } from "../types";

type Props = {
  models: ModelsResponse | null;
  status: SystemStatus | null;
  loading: boolean;
  error: string | null;
};

export function ModelsPanel({ models, status, loading, error }: Props) {
  const registry = status?.model_registry ?? [];
  const roleMap = new Map(registry.map((entry) => [entry.public_name, entry.role]));
  const enabledMap = new Map(registry.map((entry) => [entry.public_name, entry.enabled]));
  const activeModel = status?.runtime?.active_model;

  return (
    <section className="panel">
      <h2>Models</h2>
      {loading && !models ? <p>Loading models...</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      <div className="model-list">
        {(models?.data ?? []).map((model) => {
          const enabled = enabledMap.get(model.id);
          return (
            <div className="model-row" key={model.id}>
              <div>
                <div className="mono">{model.id}</div>
                <small>
                  role: {roleMap.get(model.id) ?? "unknown"} | enabled: {String(enabled ?? true)}
                </small>
              </div>
              <span className={activeModel === model.id ? "badge active" : "badge"}>
                {activeModel === model.id ? "active" : "available"}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
