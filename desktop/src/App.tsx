import { useCallback, useEffect, useState } from "react";
import { health, getConfig, getVaultFile, type Config } from "./lib/api";
import { Sidebar } from "./components/Sidebar";
import { Editor } from "./components/Editor";
import { Chat } from "./components/Chat";
import { Button } from "@/components/ui/button";
import "./App.css";

function App() {
  const [connected, setConnected] = useState(false);
  const [config, setConfig] = useState<Config | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [chatOpen, setChatOpen] = useState(true);

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

  const handleSelectFile = useCallback(async (path: string) => {
    try {
      const note = await getVaultFile(path);
      setSelectedPath(path);
      setFileContent(note.content);
    } catch (err) {
      console.error("Failed to load note:", err);
    }
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
        <div className="flex items-center gap-3 text-xs">
          {config && (
            <span className="text-muted-foreground">{config.vault_path}</span>
          )}
          <Button
            variant={chatOpen ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setChatOpen(!chatOpen)}
            className="h-6 text-xs"
          >
            Chat
          </Button>
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400" />
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        <Sidebar selectedPath={selectedPath} onSelectFile={handleSelectFile} />
        <Editor filePath={selectedPath} content={fileContent} />
        {chatOpen && <Chat />}
      </div>
    </div>
  );
}

export default App;
