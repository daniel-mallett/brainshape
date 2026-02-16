import { useEffect, useRef, useState } from "react";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers as lineNumbersExt } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { vim } from "@replit/codemirror-vim";
import { updateNoteFile } from "../lib/api";
import { brainAutocompletion, prefetchCompletions } from "../lib/completions";
import { wikilinkExtension, setWikilinkNavigate } from "../lib/wikilinks";
import { inlineMarkdownExtension } from "../lib/inlineMarkdown";
import { brainThemeExtension } from "../lib/editorTheme";
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
  keymap?: string;
  lineNumbers?: boolean;
  wordWrap?: boolean;
}

export function Editor({ filePath, content, onNavigateToNote, keymap: keymapMode = "vim", lineNumbers = false, wordWrap = true }: EditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filePathRef = useRef(filePath);
  const [editorMode, setEditorMode] = useState<EditorMode>("edit");
  const [liveContent, setLiveContent] = useState(content);

  filePathRef.current = filePath;

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

  useEffect(() => {
    prefetchCompletions();
  }, []);

  useEffect(() => {
    if (onNavigateToNote) {
      setWikilinkNavigate(onNavigateToNote);
    }
  }, [onNavigateToNote]);

  useEffect(() => {
    if (!containerRef.current || editorMode === "preview") return;

    const extensions = [
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      markdown({ codeLanguages: languages }),
      ...brainThemeExtension(),
      brainAutocompletion,
      wikilinkExtension,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const text = update.state.doc.toString();
          setLiveContent(text);
          saveToServer(text);
        }
      }),
    ];

    // Keybinding mode
    if (keymapMode === "vim") {
      extensions.unshift(vim());
    }

    // Line numbers
    if (lineNumbers) {
      extensions.push(lineNumbersExt());
    }

    // Word wrap
    if (wordWrap) {
      extensions.push(EditorView.lineWrapping);
    }

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
  }, [filePath, editorMode, keymapMode, lineNumbers, wordWrap]);

  if (!filePath) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        <div className="text-center space-y-3">
          <p className="text-sm">Select a note from the sidebar to start editing</p>
          <div className="text-xs space-y-1 text-muted-foreground/60">
            <p><kbd className="bg-muted px-1.5 py-0.5 rounded text-[11px]">Cmd+K</kbd> to search notes</p>
            <p><kbd className="bg-muted px-1.5 py-0.5 rounded text-[11px]">+</kbd> in sidebar to create a new note</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-w-0">
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
