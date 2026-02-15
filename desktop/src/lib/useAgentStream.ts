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

          // SSE uses \r\n line endings; normalize to \n before splitting
          const lines = buffer.replace(/\r\n/g, "\n").split("\n");
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

                // All data is JSON-encoded by the server
                try {
                  const parsed = JSON.parse(data);
                  if (typeof parsed === "string") {
                    // Text token
                    last.content += parsed;
                  } else if (parsed.name) {
                    // Tool call
                    last.toolCalls = [...(last.toolCalls || []), parsed];
                  }
                } catch {
                  // Fallback: treat as raw text
                  last.content += data;
                }

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

  // Index of the message currently being streamed (last assistant message during streaming)
  const streamingMessageIndex = isStreaming ? messages.length - 1 : -1;

  return { messages, isStreaming, streamingMessageIndex, sendMessage, resetSession };
}
