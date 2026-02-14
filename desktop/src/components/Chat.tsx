import { useRef, useEffect, useState, type FormEvent } from "react";
import { useAgentStream, type Message } from "../lib/useAgentStream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";

function MessageBubble({ message }: { message: Message }) {
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
        {message.content && (
          <div className="whitespace-pre-wrap">{message.content}</div>
        )}
      </div>
    </div>
  );
}

export function Chat() {
  const { messages, isStreaming, sendMessage } = useAgentStream();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

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
    <div className="w-80 flex-shrink-0 border-l border-border bg-card/30 flex flex-col">
      <div className="px-3 py-2 border-b border-border">
        <span className="text-sm font-medium">Chat</span>
      </div>

      <ScrollArea className="flex-1">
        <div ref={scrollRef} className="p-3 space-y-3">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground text-center mt-8">
              Ask Brain anything about your notes
            </p>
          )}
          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} />
          ))}
          {isStreaming && (
            <div className="flex justify-start">
              <div className="text-xs text-muted-foreground px-3 py-1">
                thinking...
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      <form onSubmit={handleSubmit} className="p-2 border-t border-border">
        <div className="flex gap-2">
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
