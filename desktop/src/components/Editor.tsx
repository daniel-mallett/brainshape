import { useEffect, useMemo, useRef, useState } from "react";
import { Compartment, EditorState } from "@codemirror/state";
import { EditorView, drawSelection, keymap, lineNumbers as lineNumbersExt } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { languages } from "@codemirror/language-data";
import { GFM } from "@lezer/markdown";
import { vim } from "@replit/codemirror-vim";
import { updateNoteFile } from "../lib/api";
import { brainshapeAutocompletion, prefetchCompletions } from "../lib/completions";
import { wikilinkExtension, setWikilinkNavigate } from "../lib/wikilinks";
import { inlineMarkdownExtension } from "../lib/inlineMarkdown";
import { brainshapeThemeExtension } from "../lib/editorTheme";
import { Streamdown } from "streamdown";
import { createCodePlugin } from "@streamdown/code";
import type { BundledTheme } from "shiki";
import remarkGfm from "remark-gfm";
import { remarkWikilinks } from "../lib/remarkWikilinks";
import { wikilinkComponents } from "../lib/WikilinkComponents";
import { useWikilinkClick } from "../lib/useWikilinkClick";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";

type SaveStatus = "idle" | "saving" | "saved" | "error";

const previewRemarkPlugins = [remarkGfm, remarkWikilinks];

interface EditorProps {
  filePath: string | null;
  content: string;
  onNavigateToNote?: (title: string) => void;
  keymap?: string;
  lineNumbers?: boolean;
  wordWrap?: boolean;
  inlineFormatting?: boolean;
  shikiTheme?: [string, string];
  canGoBack?: boolean;
  canGoForward?: boolean;
  onGoBack?: () => void;
  onGoForward?: () => void;
}

export function Editor({ filePath, content, onNavigateToNote, keymap: keymapMode = "vim", lineNumbers = false, wordWrap = true, inlineFormatting = false, shikiTheme, canGoBack, canGoForward, onGoBack, onGoForward }: EditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filePathRef = useRef(filePath);
  const liveContentRef = useRef(content);
  const inlineCompartmentRef = useRef(new Compartment());
  const themeCompartmentRef = useRef(new Compartment());
  const [showPreview, setShowPreview] = useState(false);
  const [liveContent, setLiveContent] = useState(content);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const saveStatusTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const previewPlugins = useMemo(() => {
    const themes = (shikiTheme || ["min-light", "min-dark"]) as [BundledTheme, BundledTheme];
    return { code: createCodePlugin({ themes }) };
  }, [shikiTheme]);

  filePathRef.current = filePath;

  useEffect(() => {
    setLiveContent(content);
    liveContentRef.current = content;

    // If editor exists and content changed externally (not from typing),
    // update the editor document to reflect the new content.
    const view = viewRef.current;
    if (view) {
      const currentDoc = view.state.doc.toString();
      if (content !== currentDoc) {
        view.dispatch({
          changes: { from: 0, to: currentDoc.length, insert: content },
        });
      }
    }
  }, [content]);

  function saveToServer(text: string) {
    const currentPath = filePathRef.current;
    if (!currentPath) return;
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
    setSaveStatus("saving");
    saveTimeoutRef.current = setTimeout(async () => {
      try {
        await updateNoteFile(currentPath, text);
        setSaveStatus("saved");
        if (saveStatusTimeoutRef.current) clearTimeout(saveStatusTimeoutRef.current);
        saveStatusTimeoutRef.current = setTimeout(() => setSaveStatus("idle"), 2000);
      } catch (err) {
        console.error("Save failed:", err);
        if (saveStatusTimeoutRef.current) clearTimeout(saveStatusTimeoutRef.current);
        setSaveStatus("error");
      }
    }, 1000);
  }

  const wikilinkRef = useWikilinkClick(onNavigateToNote);

  useEffect(() => {
    prefetchCompletions();
  }, []);

  useEffect(() => {
    if (onNavigateToNote) {
      setWikilinkNavigate(onNavigateToNote);
    }
  }, [onNavigateToNote]);

  // Main editor creation — only recreates for filePath, keymap, lineNumbers, wordWrap changes
  useEffect(() => {
    if (!containerRef.current) return;

    const extensions = [
      drawSelection(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      markdown({ codeLanguages: languages, extensions: GFM }),
      themeCompartmentRef.current.of(brainshapeThemeExtension()),
      brainshapeAutocompletion,
      wikilinkExtension,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          const text = update.state.doc.toString();
          liveContentRef.current = text;
          setLiveContent(text);
          saveToServer(text);
        }
      }),
      // Inline formatting via compartment — toggled without recreating editor
      inlineCompartmentRef.current.of(
        inlineFormatting ? inlineMarkdownExtension : []
      ),
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

    const state = EditorState.create({
      doc: liveContentRef.current,
      extensions,
    });

    const view = new EditorView({
      state,
      parent: containerRef.current,
    });

    viewRef.current = view;

    return () => {
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      if (saveStatusTimeoutRef.current) clearTimeout(saveStatusTimeoutRef.current);
      view.destroy();
      viewRef.current = null;
    };
  }, [filePath, keymapMode, lineNumbers, wordWrap]);

  // Reconfigure inline formatting compartment without recreating editor
  useEffect(() => {
    viewRef.current?.dispatch({
      effects: inlineCompartmentRef.current.reconfigure(
        inlineFormatting ? inlineMarkdownExtension : []
      ),
    });
  }, [inlineFormatting]);

  // Observe dark/light mode changes and reconfigure the theme compartment
  useEffect(() => {
    const observer = new MutationObserver(() => {
      viewRef.current?.dispatch({
        effects: themeCompartmentRef.current.reconfigure(
          brainshapeThemeExtension()
        ),
      });
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

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
    <div ref={wikilinkRef} className="h-full flex flex-col min-w-0">
      <div className="px-4 py-1.5 border-b border-border text-sm text-muted-foreground flex items-center justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <div className="flex gap-0.5 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0"
              disabled={!canGoBack}
              onClick={onGoBack}
              title="Go back (Cmd+[)"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path fillRule="evenodd" d="M9.78 4.22a.75.75 0 0 1 0 1.06L7.06 8l2.72 2.72a.75.75 0 1 1-1.06 1.06L5.47 8.53a.75.75 0 0 1 0-1.06l3.25-3.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
              </svg>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-5 w-5 p-0"
              disabled={!canGoForward}
              onClick={onGoForward}
              title="Go forward (Cmd+])"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path fillRule="evenodd" d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
              </svg>
            </Button>
          </div>
          <span className="truncate">{filePath}</span>
          {saveStatus !== "idle" && (
            <span className={`text-xs shrink-0 ${saveStatus === "error" ? "text-destructive" : "text-muted-foreground"}`}>
              {saveStatus === "saving" && "Saving..."}
              {saveStatus === "saved" && "Saved"}
              {saveStatus === "error" && "Save failed"}
            </span>
          )}
        </div>
        <div className="flex gap-0.5">
          <Button
            variant={showPreview ? "ghost" : "secondary"}
            size="sm"
            className="h-5 text-xs px-2"
            onClick={() => setShowPreview(false)}
          >
            Edit
          </Button>
          <Button
            variant={showPreview ? "secondary" : "ghost"}
            size="sm"
            className="h-5 text-xs px-2"
            onClick={() => setShowPreview(true)}
          >
            Preview
          </Button>
        </div>
      </div>

      {showPreview && (
        <ScrollArea className="flex-1 overflow-hidden">
          <div className="p-6 max-w-prose mx-auto">
            <Streamdown
              className="sdm-chat"
              plugins={previewPlugins}
              remarkPlugins={previewRemarkPlugins}
              components={wikilinkComponents}
            >
              {liveContent}
            </Streamdown>
          </div>
        </ScrollArea>
      )}
      <div
        className="flex-1 overflow-hidden flex justify-center"
        style={{ display: showPreview ? "none" : undefined }}
      >
        <div ref={containerRef} className="h-full w-full max-w-[65ch]" />
      </div>
    </div>
  );
}
