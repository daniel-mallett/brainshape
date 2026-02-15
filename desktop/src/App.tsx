import { useCallback, useEffect, useState } from "react";
import { health, getConfig, getNoteFile, getNoteFiles, syncStructural, type Config } from "./lib/api";
import { Sidebar } from "./components/Sidebar";
import { Editor } from "./components/Editor";
import { Chat } from "./components/Chat";
import { GraphPanel } from "./components/GraphPanel";
import { MemoryPanel } from "./components/MemoryPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { CommandPalette } from "./components/CommandPalette";
import { Button } from "@/components/ui/button";
import "./App.css";

type ActiveView = "editor" | "graph" | "memory" | "settings";

function App() {
  const [connected, setConnected] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [chatOpen, setChatOpen] = useState(true);
  const [activeView, setActiveView] = useState<ActiveView>("editor");
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    async function checkConnection() {
      try {
        await health();
        setConnected(true);
        const cfg = await getConfig();
        setConfig(cfg);
      } catch {
        setConnected(false);
      }
    }

    checkConnection();
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectFile = useCallback(
    async (path: string) => {
      try {
        const note = await getNoteFile(path);
        setSelectedPath(path);
        setFileContent(note.content);
        if (activeView !== "editor") {
          setActiveView("editor");
        }
      } catch (err) {
        console.error("Failed to load note:", err);
      }
    },
    [activeView]
  );

  const handleNavigateToNote = useCallback(
    (path: string) => {
      handleSelectFile(path);
      setActiveView("editor");
    },
    [handleSelectFile]
  );

  // Navigate by note title (for wikilinks in editor)
  const handleNavigateByTitle = useCallback(
    async (title: string) => {
      try {
        const { files } = await getNoteFiles();
        const match = files.find((f) => f.title === title);
        if (match) {
          handleSelectFile(match.path);
        }
      } catch (err) {
        console.error("Failed to navigate to note:", err);
      }
    },
    [handleSelectFile]
  );

  // Cmd+K to open command palette
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleCreateNote = useCallback(() => {
    // Trigger the sidebar's create flow by programmatically focusing
    // For now, we'll just switch to editor view — the sidebar has the + button
    setActiveView("editor");
  }, []);

  const handleSync = useCallback(() => {
    syncStructural().catch(console.error);
  }, []);

  if (!connected) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-center">
          <p className="text-destructive mb-2">Cannot connect to Brain server</p>
          <p className="text-muted-foreground text-sm">
            Run:{" "}
            <code className="bg-muted px-2 py-0.5 rounded text-sm">
              uv run python -m brain.server
            </code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <header className="flex items-center justify-between px-4 py-1.5 border-b border-border">
        <h1 className="text-sm font-semibold">Brain</h1>
        <div className="flex items-center gap-1 text-xs">
          {config && (
            <span className="text-muted-foreground mr-2">
              {config.notes_path}
            </span>
          )}
          <Button
            variant={activeView === "editor" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveView("editor")}
            className="h-6 text-xs"
          >
            Editor
          </Button>
          <Button
            variant={activeView === "graph" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveView("graph")}
            className="h-6 text-xs"
          >
            Graph
          </Button>
          <Button
            variant={activeView === "memory" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveView("memory")}
            className="h-6 text-xs"
          >
            Memory
          </Button>
          <Button
            variant={activeView === "settings" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveView("settings")}
            className="h-6 text-xs"
          >
            Settings
          </Button>
          <div className="border-l border-border h-4 mx-1" />
          <Button
            variant={chatOpen ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setChatOpen(!chatOpen)}
            className="h-6 text-xs"
          >
            Chat
          </Button>
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 ml-1" />
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        <Sidebar selectedPath={selectedPath} onSelectFile={handleSelectFile} />

        {activeView === "editor" && (
          <Editor filePath={selectedPath} content={fileContent} onNavigateToNote={handleNavigateByTitle} />
        )}
        {activeView === "graph" && (
          <GraphPanel onNavigateToNote={handleNavigateToNote} />
        )}
        {activeView === "memory" && <MemoryPanel />}
        {activeView === "settings" && <SettingsPanel />}

        {chatOpen && <Chat />}
      </div>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectNote={handleSelectFile}
        onCreateNote={handleCreateNote}
        onSwitchView={(v) => setActiveView(v as ActiveView)}
        onSync={handleSync}
      />
    </div>
  );
}

export default App;
