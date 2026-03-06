import { useMemo, useState } from "react";

import { createChatCompletion } from "../lib/api";
import type { ChatCompletionResponse, ModelsResponse } from "../types";

type Props = {
  models: ModelsResponse | null;
};

type ChatEntry = {
  id: string;
  prompt: string;
  response?: string;
  error?: string;
  sessionId?: string;
  sessionDebug?: Record<string, unknown>;
  ragDebug?: Record<string, unknown>;
};

export function ChatTestPanel({ models }: Props) {
  const modelOptions = useMemo(() => (models?.data ?? []).map((model) => model.id), [models]);
  const [model, setModel] = useState<string>("local-general");
  const [sessionId, setSessionId] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [entries, setEntries] = useState<ChatEntry[]>([]);

  async function onSend() {
    if (!input.trim() || sending) {
      return;
    }

    const prompt = input.trim();
    const activeSessionId = sessionId.trim() || undefined;
    const entry: ChatEntry = { id: crypto.randomUUID(), prompt, sessionId: activeSessionId };
    setEntries((prev) => [entry, ...prev]);
    setInput("");
    setSending(true);

    try {
      const response: ChatCompletionResponse = await createChatCompletion({
        model,
        message: prompt,
        sessionId: activeSessionId,
      });
      const answer = response.choices[0]?.message?.content ?? "(empty response)";
      const responseSessionId = response.portable_ai?.session_id;
      if (responseSessionId) {
        setSessionId(responseSessionId);
      }
      setEntries((prev) =>
        prev.map((item) =>
          item.id === entry.id
            ? {
                ...item,
                response: answer,
                sessionId: responseSessionId ?? item.sessionId,
                sessionDebug: response.portable_ai?.session_debug,
                ragDebug: response.rag_debug,
              }
            : item
        )
      );
    } catch (error) {
      setEntries((prev) =>
        prev.map((item) =>
          item.id === entry.id ? { ...item, error: (error as Error).message || "Chat request failed" } : item
        )
      );
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="panel panel-wide">
      <h2>Chat Test</h2>
      <div className="chat-controls">
        <label>
          Model
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            {(modelOptions.length ? modelOptions : ["local-general"]).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label>
          Session ID
          <input
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
            placeholder="Auto-generated if empty"
          />
        </label>
        <button onClick={onSend} disabled={sending || !input.trim()}>
          {sending ? "Sending..." : "Send"}
        </button>
        <button type="button" onClick={() => setSessionId("")} disabled={sending}>
          New Session
        </button>
      </div>
      <textarea
        value={input}
        onChange={(event) => setInput(event.target.value)}
        placeholder="Enter a chat test prompt"
      />

      <div className="chat-output">
        {entries.map((entry) => (
          <div className="chat-entry" key={entry.id}>
            <p>
              <strong>User:</strong> {entry.prompt}
            </p>
            {entry.sessionId ? (
              <p>
                <strong>Session:</strong> {entry.sessionId}
              </p>
            ) : null}
            {entry.response ? (
              <p>
                <strong>Assistant:</strong> {entry.response}
              </p>
            ) : null}
            {entry.error ? <p className="error-text">{entry.error}</p> : null}
            {entry.sessionDebug ? <pre>{JSON.stringify(entry.sessionDebug, null, 2)}</pre> : null}
            {entry.ragDebug ? <pre>{JSON.stringify(entry.ragDebug, null, 2)}</pre> : null}
          </div>
        ))}
      </div>
    </section>
  );
}
