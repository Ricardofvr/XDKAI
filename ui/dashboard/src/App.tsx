import { useEffect, useMemo, useState } from "react";

import { getModels, getSystemStatus } from "./lib/api";
import {
  ChatTestPanel,
  DiagnosticsPanel,
  LayoutShell,
  ModelsPanel,
  RagIndexPanel,
  RetrievalTestPanel,
  SystemOverviewPanel,
} from "./components";
import type { ModelsResponse, SystemStatus } from "./types";

export function App() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [models, setModels] = useState<ModelsResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  async function loadStatus() {
    setStatusLoading(true);
    try {
      const payload = await getSystemStatus();
      setStatus(payload);
      setStatusError(null);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (error) {
      setStatusError((error as Error).message || "Status fetch failed");
    } finally {
      setStatusLoading(false);
    }
  }

  async function loadModels() {
    setModelsLoading(true);
    try {
      const payload = await getModels();
      setModels(payload);
      setModelsError(null);
    } catch (error) {
      setModelsError((error as Error).message || "Models fetch failed");
    } finally {
      setModelsLoading(false);
    }
  }

  async function refreshAll() {
    await Promise.all([loadStatus(), loadModels()]);
  }

  useEffect(() => {
    void refreshAll();
    const timer = window.setInterval(() => {
      void loadStatus();
    }, 8000);
    return () => window.clearInterval(timer);
  }, []);

  const retrievalTopK = useMemo(() => status?.rag_index?.retrieval?.top_k ?? 3, [status]);

  return (
    <LayoutShell lastUpdated={lastUpdated} onRefresh={refreshAll} statusError={statusError}>
      <SystemOverviewPanel status={status} loading={statusLoading} />
      <RagIndexPanel ragIndex={status?.rag_index} />
      <DiagnosticsPanel status={status} />
      <ModelsPanel models={models} status={status} loading={modelsLoading} error={modelsError} />
      <ChatTestPanel models={models} />
      <RetrievalTestPanel defaultTopK={retrievalTopK} />
    </LayoutShell>
  );
}
