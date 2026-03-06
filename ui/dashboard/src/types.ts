export type RuntimeStatus = {
  selected_provider?: string;
  active_provider?: string;
  provider?: string;
  mode?: string;
  state?: string;
  fallback_engaged?: boolean;
  generation_ready?: boolean;
  embedding_ready?: boolean;
  active_model?: string | null;
};

export type RagIndexStatus = {
  initialized?: boolean;
  index_location?: string;
  total_documents?: number;
  total_vectors?: number;
  embedding_model?: string;
  last_indexed_at?: string | null;
  retrieval?: {
    top_k?: number;
    similarity_metric?: string;
    min_similarity?: number;
  };
  search_enabled?: boolean;
};

export type RagChatStatus = {
  enabled?: boolean;
  retrieval_fetch_k?: number;
  max_context_chunks?: number;
  max_context_characters?: number;
  max_chunks_per_document?: number;
  deduplicate_results?: boolean;
  near_duplicate_threshold?: number;
  min_similarity?: number;
  index_ready?: boolean;
  retrieval_enabled?: boolean;
  include_source_metadata?: boolean;
  debug_retrieval?: boolean;
  last_retrieval_diagnostics?: Record<string, unknown> | null;
};

export type ModelRegistryEntry = {
  public_name: string;
  provider_model_id: string;
  role: string;
  enabled: boolean;
  metadata?: Record<string, unknown>;
};

export type SystemStatus = {
  environment?: string;
  offline_mode?: boolean;
  runtime?: RuntimeStatus;
  chat_orchestration?: {
    sessions?: {
      storage_mode?: string;
      sessions_in_memory?: number;
      sessions_persisted?: number;
    };
  };
  model_registry?: ModelRegistryEntry[];
  rag_index?: RagIndexStatus;
  rag_chat?: RagChatStatus;
  startup_state?: Record<string, boolean>;
};

export type OpenAIModel = {
  id: string;
  object?: string;
  created?: number;
  owned_by?: string;
};

export type ModelsResponse = {
  object: string;
  data: OpenAIModel[];
};

export type ChatMessage = {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
};

export type ChatCompletionResponse = {
  id: string;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finish_reason: string;
  }>;
  portable_ai?: {
    session_id?: string;
    session_created?: boolean;
    session_debug?: Record<string, unknown>;
  };
  rag_debug?: Record<string, unknown>;
};

export type RetrievalResult = {
  rank: number;
  similarity: number;
  document_id: string;
  source_file: string;
  chunk_index: number;
  chunk_text: string;
  chunk_preview: string;
};

export type RetrievalResponse = {
  query: string;
  embedding_model: string;
  similarity_metric: string;
  top_k: number;
  min_similarity: number;
  result_count: number;
  results: RetrievalResult[];
};
