import { useCallback, useRef, useState } from "react";
import { initSession } from "./api";

const BASE_URL = "http://127.0.0.1:8765";

export type MessagePart =
  | { type: "text"; content: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> };

export interface Message {
  role: "user" | "assistant";
  content: string;
  parts?: MessagePart[];
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

      const assistantMsg: Message = { role: "assistant", content: "", parts: [] };
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
              continue;
            }
            if (line.startsWith("data: ")) {
              const data = line.slice(6);

              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };
                const parts = [...(last.parts || [])];

                if (data === "") {
                  return updated;
                }

                try {
                  const parsed = JSON.parse(data);
                  if (typeof parsed === "string") {
                    // Text token — append to current text part or start a new one
                    const lastPart = parts[parts.length - 1];
                    if (lastPart && lastPart.type === "text") {
                      parts[parts.length - 1] = { ...lastPart, content: lastPart.content + parsed };
                    } else {
                      parts.push({ type: "text", content: parsed });
                    }
                    last.content += parsed;
                  } else if (parsed.name) {
                    // Tool call — creates a boundary so next text starts a new part
                    parts.push({ type: "tool_call", name: parsed.name, args: parsed.args || {} });
                  }
                } catch {
                  // Fallback: treat as raw text
                  const lastPart = parts[parts.length - 1];
                  if (lastPart && lastPart.type === "text") {
                    parts[parts.length - 1] = { ...lastPart, content: lastPart.content + data };
                  } else {
                    parts.push({ type: "text", content: data });
                  }
                  last.content += data;
                }

                last.parts = parts;
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
          const parts = [...(last.parts || [])];
          parts.push({ type: "text", content: `\n\nError: ${err}` });
          last.parts = parts;
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
