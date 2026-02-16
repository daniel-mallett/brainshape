import { useRef, useEffect, useState, type FormEvent } from "react";
import { useAgentStream, type Message } from "../lib/useAgentStream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { VoiceRecorder } from "./VoiceRecorder";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { remarkWikilinks } from "../lib/remarkWikilinks";
import { wikilinkComponents } from "../lib/WikilinkComponents";
import { useWikilinkClick } from "../lib/useWikilinkClick";

const streamdownPlugins = { code };
const wikilinkRemarkPlugins = [remarkWikilinks];

function MessageBubble({
  message,
  isAnimating,
}: {
  message: Message;
  isAnimating: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card text-card-foreground"
        }`}
      >
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mb-1.5 space-y-1">
            {message.toolCalls.map((tc, i) => (
              <div
                key={i}
                className="text-xs text-muted-foreground bg-muted rounded px-2 py-1 font-mono"
              >
                → {tc.name}({Object.keys(tc.args).join(", ")})
              </div>
            ))}
          </div>
        )}
        {message.content &&
          (isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <Streamdown
              animated
              plugins={streamdownPlugins}
              remarkPlugins={wikilinkRemarkPlugins}
              components={wikilinkComponents}
              isAnimating={isAnimating}
            >
              {message.content}
            </Streamdown>
          ))}
      </div>
    </div>
  );
}

export function Chat({ onNavigateToNote }: { onNavigateToNote?: (title: string) => void }) {
  const { messages, isStreaming, streamingMessageIndex, sendMessage } =
    useAgentStream();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const wikilinkRef = useWikilinkClick(onNavigateToNote);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    sendMessage(text);
  };

  return (
    <div ref={wikilinkRef} className="h-full flex flex-col min-h-0 bg-card/30">
      <div className="px-3 py-2 border-b border-border">
        <span className="text-sm font-medium">Chat</span>
      </div>

      <ScrollArea className="flex-1 overflow-hidden">
        <div ref={scrollRef} className="p-3 space-y-3">
          {messages.length === 0 && (
            <div className="text-center mt-8 space-y-4">
              <p className="text-sm text-muted-foreground">
                Ask Brain anything about your notes
              </p>
              <div className="flex flex-wrap gap-2 justify-center px-2">
                {[
                  "What are my most connected notes?",
                  "Summarize my recent notes",
                  "What topics do I write about most?",
                  "What should I write about next?",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    disabled={isStreaming}
                    className="px-3 py-1.5 text-xs rounded-md border border-border bg-card hover:bg-accent hover:text-accent-foreground transition-colors disabled:opacity-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              message={msg}
              isAnimating={i === streamingMessageIndex}
            />
          ))}
          {isStreaming && (() => {
            const lastMsg = messages[messages.length - 1];
            const hasContent = lastMsg?.role === "assistant" &&
              (lastMsg.content !== "" || (lastMsg.toolCalls && lastMsg.toolCalls.length > 0));
            return !hasContent ? (
              <div className="flex justify-start">
                <div className="text-xs text-muted-foreground px-3 py-1">
                  thinking...
                </div>
              </div>
            ) : null;
          })()}
        </div>
      </ScrollArea>

      <form onSubmit={handleSubmit} className="p-2 border-t border-border">
        <div className="flex gap-2">
          <VoiceRecorder
            onTranscription={(text) => {
              setInput((prev) => (prev ? `${prev} ${text}` : text));
            }}
            disabled={isStreaming}
          />
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            disabled={isStreaming}
            className="h-8 text-sm"
          />
          <Button
            type="submit"
            size="sm"
            disabled={isStreaming || !input.trim()}
          >
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}
