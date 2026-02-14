import { useCallback, useRef, useState } from "react";
import { initSession } from "./api";

const BASE_URL = "http://127.0.0.1:8765";

export interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: { name: string; args: Record<string, unknown> }[];
}

export function useAgentStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  const ensureSession = useCallback(async () => {
    if (!sessionIdRef.current) {
      const { session_id } = await initSession();
      sessionIdRef.current = session_id;
    }
    return sessionIdRef.current;
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const sessionId = await ensureSession();

      setMessages((prev) => [...prev, { role: "user", content: text }]);
      setIsStreaming(true);

      const assistantMsg: Message = { role: "assistant", content: "", toolCalls: [] };
      setMessages((prev) => [...prev, assistantMsg]);

      try {
        const res = await fetch(`${BASE_URL}/agent/message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message: text }),
        });

        if (!res.ok) {
          throw new Error(`${res.status}: ${await res.text()}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              // SSE event type — data follows on next line
              continue;
            }
            if (line.startsWith("data: ")) {
              const data = line.slice(6);

              // Find the most recent event type from buffer context
              // SSE format: event: <type>\ndata: <payload>
              // We need to track the event type
              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };

                if (data === "") {
                  // done event
                  return updated;
                }

                // Try to parse as JSON (tool_call events)
                try {
                  const parsed = JSON.parse(data);
                  if (parsed.name) {
                    last.toolCalls = [...(last.toolCalls || []), parsed];
                    updated[updated.length - 1] = last;
                    return updated;
                  }
                } catch {
                  // not JSON, treat as text
                }

                last.content += data;
                updated[updated.length - 1] = last;
                return updated;
              });
            }
          }
        }
      } catch (err) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          last.content += `\n\nError: ${err}`;
          updated[updated.length - 1] = last;
          return updated;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [ensureSession]
  );

  const resetSession = useCallback(() => {
    sessionIdRef.current = null;
    setMessages([]);
  }, []);

  return { messages, isStreaming, sendMessage, resetSession };
}
