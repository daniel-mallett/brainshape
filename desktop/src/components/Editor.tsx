import { useEffect, useRef, useState } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { vim } from "@replit/codemirror-vim";
import { oneDark } from "@codemirror/theme-one-dark";
import { updateNoteFile } from "../lib/api";
import { brainAutocompletion, prefetchCompletions } from "../lib/completions";
import { wikilinkExtension, setWikilinkNavigate } from "../lib/wikilinks";
import { inlineMarkdownExtension } from "../lib/inlineMarkdown";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";

type EditorMode = "edit" | "inline" | "preview";

const streamdownPlugins = { code };

interface EditorProps {
  filePath: string | null;
  content: string;
  onNavigateToNote?: (title: string) => void;
}

export function Editor({ filePath, content, onNavigateToNote }: EditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filePathRef = useRef(filePath);
  const [editorMode, setEditorMode] = useState<EditorMode>("edit");
  const [liveContent, setLiveContent] = useState(content);

  filePathRef.current = filePath;

  // Sync content prop into liveContent when file changes
  useEffect(() => {
    setLiveContent(content);
  }, [content]);

  function saveToServer(text: string) {
    if (!filePathRef.current) return;
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    saveTimeoutRef.current = setTimeout(() => {
      updateNoteFile(filePathRef.current!, text).catch(console.error);
    }, 1000);
  }

  // Pre-fetch completions cache on mount so first keystroke has data
  useEffect(() => {
    prefetchCompletions();
  }, []);

  // Set up wikilink navigation callback
  useEffect(() => {
    if (onNavigateToNote) {
      setWikilinkNavigate(onNavigateToNote);
    }
  }, [onNavigateToNote]);

  useEffect(() => {
    if (!containerRef.current || editorMode === "preview") return;

    const extensions = [
      vim(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      markdown({ codeLanguages: languages }),
      oneDark,
      brainAutocompletion,
      wikilinkExtension,
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const text = update.state.doc.toString();
          setLiveContent(text);
          saveToServer(text);
        }
      }),
      EditorView.theme({
        "&": {
          height: "100%",
          fontSize: "14px",
        },
        ".cm-scroller": {
          fontFamily:
            "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        },
        ".cm-content": {
          padding: "16px 0",
        },
        ".cm-gutters": {
          backgroundColor: "transparent",
          border: "none",
        },
      }),
    ];

    if (editorMode === "inline") {
      extensions.push(inlineMarkdownExtension);
    }

    const state = EditorState.create({
      doc: content,
      extensions,
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      view.destroy();
      viewRef.current = null;
    };
  }, [filePath, editorMode]); // Re-create editor when file or mode changes

  if (!filePath) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        <p>Select a note to edit</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <div className="px-4 py-1.5 border-b border-border text-sm text-muted-foreground flex items-center justify-between">
        <span>{filePath}</span>
        <div className="flex gap-0.5">
          {(["edit", "inline", "preview"] as const).map((mode) => (
            <Button
              key={mode}
              variant={editorMode === mode ? "secondary" : "ghost"}
              size="sm"
              className="h-5 text-xs px-2"
              onClick={() => setEditorMode(mode)}
            >
              {mode === "edit"
                ? "Edit"
                : mode === "inline"
                  ? "Inline"
                  : "Preview"}
            </Button>
          ))}
        </div>
      </div>

      {editorMode === "preview" ? (
        <ScrollArea className="flex-1 overflow-hidden">
          <div className="p-6 max-w-prose">
            <Streamdown plugins={streamdownPlugins}>
              {liveContent}
            </Streamdown>
          </div>
        </ScrollArea>
      ) : (
        <div ref={containerRef} className="flex-1 overflow-hidden" />
      )}
    </div>
  );
}
