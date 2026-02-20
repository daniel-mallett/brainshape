import { useRef, useEffect, useState, useMemo, type FormEvent } from "react";
import { useAgentStream, type Message } from "../lib/useAgentStream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { VoiceRecorder } from "./VoiceRecorder";
import { Streamdown } from "streamdown";
import { createCodePlugin } from "@streamdown/code";
import type { BundledTheme } from "shiki";
import remarkGfm from "remark-gfm";
import { remarkWikilinks } from "../lib/remarkWikilinks";
import { wikilinkComponents } from "../lib/WikilinkComponents";
import { useWikilinkClick } from "../lib/useWikilinkClick";

const streamdownRemarkPlugins = [remarkGfm, remarkWikilinks];

function MessageBubble({
  message,
  isAnimating,
  plugins,
}: {
  message: Message;
  isAnimating: boolean;
  plugins: Record<string, unknown>;
}) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-primary text-primary-foreground">
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
      </div>
    );
  }

  // Assistant message — render parts in natural order
  const parts = message.parts || [];

  // Find last text part index for streaming animation
  let lastTextIdx = -1;
  for (let i = parts.length - 1; i >= 0; i--) {
    if (parts[i].type === "text") {
      lastTextIdx = i;
      break;
    }
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-lg px-3 py-2 text-sm bg-card text-card-foreground">
        {parts.map((part, i) =>
          part.type === "tool_call" ? (
            <div
              key={i}
              className="text-xs text-muted-foreground bg-muted rounded px-2 py-1 font-mono my-1.5"
            >
              → {part.name}({Object.keys(part.args).join(", ")})
            </div>
          ) : (
            <Streamdown
              key={i}
              animated
              className="sdm-chat"
              plugins={plugins}
              remarkPlugins={streamdownRemarkPlugins}
              components={wikilinkComponents}
              isAnimating={isAnimating && i === lastTextIdx}
            >
              {part.content}
            </Streamdown>
          )
        )}
      </div>
    </div>
  );
}

export function Chat({ onNavigateToNote, shikiTheme, settings, onOpenSettings }: {
  onNavigateToNote?: (title: string) => void;
  shikiTheme?: [string, string];
  settings?: import("../lib/api").Settings | null;
  onOpenSettings?: () => void;
}) {
  const { messages, isStreaming, streamingMessageIndex, sendMessage, resetSession } =
    useAgentStream();
  const [input, setInput] = useState("");
  const scrollEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const userScrolledUpRef = useRef(false);
  const wikilinkRef = useWikilinkClick(onNavigateToNote);

  const streamdownPlugins = useMemo(() => {
    const themes = (shikiTheme || ["min-light", "min-dark"]) as [BundledTheme, BundledTheme];
    return { code: createCodePlugin({ themes }) };
  }, [shikiTheme]);

  // Track whether user has scrolled up from the bottom
  useEffect(() => {
    const el = scrollAreaRef.current?.querySelector("[data-radix-scroll-area-viewport]");
    if (!el) return;
    const handleScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      userScrolledUpRef.current = distanceFromBottom > 80;
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, []);

  // Reset scroll lock when streaming ends or new messages start
  useEffect(() => {
    if (!isStreaming) userScrolledUpRef.current = false;
  }, [isStreaming]);

  useEffect(() => {
    if (!userScrolledUpRef.current) {
      scrollEndRef.current?.scrollIntoView({ behavior: "instant" });
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
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <span className="text-sm font-medium">Chat</span>
        {messages.length > 0 && (
          <button
            onClick={resetSession}
            disabled={isStreaming}
            title="New chat"
            aria-label="New chat"
            className="p-1 rounded hover:bg-accent text-muted-foreground hover:text-accent-foreground transition-colors disabled:opacity-50"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </button>
        )}
      </div>

      <ScrollArea ref={scrollAreaRef} className="flex-1 overflow-hidden">
        <div className="p-3 space-y-3">
          {messages.length === 0 && (
            <div className="text-center mt-8 space-y-4">
              <p className="text-sm text-muted-foreground">
                Ask Brainshape anything about your notes
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
              plugins={streamdownPlugins}
            />
          ))}
          {isStreaming && (() => {
            const lastMsg = messages[messages.length - 1];
            const hasContent = lastMsg?.role === "assistant" &&
              (lastMsg.parts && lastMsg.parts.length > 0);
            return !hasContent ? (
              <div className="flex justify-start">
                <div className="text-xs text-muted-foreground px-3 py-1">
                  thinking...
                </div>
              </div>
            ) : null;
          })()}
          <div ref={scrollEndRef} />
        </div>
      </ScrollArea>

      <form onSubmit={handleSubmit} className="p-2 border-t border-border">
        <div className="flex gap-2">
          <VoiceRecorder
            onTranscription={(text) => {
              setInput((prev) => (prev ? `${prev} ${text}` : text));
            }}
            disabled={isStreaming}
            settings={settings ?? null}
            onOpenSettings={onOpenSettings ?? (() => {})}
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
