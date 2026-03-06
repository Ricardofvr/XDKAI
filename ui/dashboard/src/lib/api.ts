import type {
  ChatCompletionResponse,
  ModelsResponse,
  RetrievalResponse,
  SystemStatus,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMessage = payload?.error?.message || `Request failed (${response.status})`;
    throw new Error(errorMessage);
  }
  return payload as T;
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return request<SystemStatus>("/system/status");
}

export async function getModels(): Promise<ModelsResponse> {
  return request<ModelsResponse>("/v1/models");
}

export async function createChatCompletion(input: {
  model: string;
  message: string;
}): Promise<ChatCompletionResponse> {
  return request<ChatCompletionResponse>("/v1/chat/completions", {
    method: "POST",
    body: JSON.stringify({
      model: input.model,
      messages: [{ role: "user", content: input.message }],
      stream: false,
    }),
  });
}

export async function searchRetrieval(input: {
  query: string;
  topK?: number;
}): Promise<RetrievalResponse> {
  return request<RetrievalResponse>("/internal/rag/search", {
    method: "POST",
    body: JSON.stringify({
      query: input.query,
      top_k: input.topK,
    }),
  });
}
