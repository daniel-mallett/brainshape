import { useCallback, useEffect, useRef, useState } from "react";
import { Group, Panel, Separator, useDefaultLayout, type PanelImperativeHandle } from "react-resizable-panels";
import { health, getConfig, getNoteFile, getNoteFiles, getSettings, syncStructural, type Config, type HealthStatus, type Settings } from "./lib/api";
import { applyTheme, BUILTIN_THEMES, DEFAULT_THEME, THEME_MIGRATION, type Theme } from "./lib/themes";
import { Sidebar, type SidebarHandle } from "./components/Sidebar";
import { Editor } from "./components/Editor";
import { Chat } from "./components/Chat";
import { GraphPanel } from "./components/GraphPanel";
import { MemoryPanel } from "./components/MemoryPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { CommandPalette } from "./components/CommandPalette";
import { MeetingRecorder } from "./components/MeetingRecorder";
import { SearchPanel } from "./components/SearchPanel";
import { SetupScreen } from "./components/SetupScreen";
import { Button } from "@/components/ui/button";
import "./App.css";

type ActiveView = "editor" | "graph" | "memory" | "search";

function GearIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={className || "w-4 h-4"}>
      <path fillRule="evenodd" d="M7.84 1.804A1 1 0 0 1 8.82 1h2.36a1 1 0 0 1 .98.804l.331 1.652a6.993 6.993 0 0 1 1.929 1.115l1.598-.54a1 1 0 0 1 1.186.447l1.18 2.044a1 1 0 0 1-.205 1.251l-1.267 1.113a7.047 7.047 0 0 1 0 2.228l1.267 1.113a1 1 0 0 1 .206 1.25l-1.18 2.045a1 1 0 0 1-1.187.447l-1.598-.54a6.993 6.993 0 0 1-1.929 1.115l-.33 1.652a1 1 0 0 1-.98.804H8.82a1 1 0 0 1-.98-.804l-.331-1.652a6.993 6.993 0 0 1-1.929-1.115l-1.598.54a1 1 0 0 1-1.186-.447l-1.18-2.044a1 1 0 0 1 .205-1.251l1.267-1.114a7.05 7.05 0 0 1 0-2.227L1.821 7.773a1 1 0 0 1-.206-1.25l1.18-2.045a1 1 0 0 1 1.187-.447l1.598.54A6.992 6.992 0 0 1 7.51 3.456l.33-1.652ZM10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" clipRule="evenodd" />
    </svg>
  );
}

function MeetingIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className={className || "w-4 h-4"}>
      <path d="M7 4a3 3 0 0 1 6 0v6a3 3 0 1 1-6 0V4Z" />
      <path d="M5.5 9.643a.75.75 0 0 0-1.5 0V10c0 3.06 2.29 5.585 5.25 5.954V17.5h-1.5a.75.75 0 0 0 0 1.5h4.5a.75.75 0 0 0 0-1.5h-1.5v-1.546A6.001 6.001 0 0 0 16 10v-.357a.75.75 0 0 0-1.5 0V10a4.5 4.5 0 0 1-9 0v-.357Z" />
    </svg>
  );
}

/** Resolve the active theme from settings, migrating old names and searching custom themes. */
function resolveTheme(settings: Settings | null): Theme {
  if (!settings?.theme || Object.keys(settings.theme).length === 0) {
    return DEFAULT_THEME;
  }
  // Migrate old theme names
  let themeName = settings.theme.name || "";
  if (themeName in THEME_MIGRATION) {
    themeName = THEME_MIGRATION[themeName];
  }
  // Search built-in themes, then custom themes
  const base =
    BUILTIN_THEMES.find((t) => t.name === themeName) ||
    (settings.custom_themes || []).find((t) => t.name === themeName) ||
    DEFAULT_THEME;
  // Merge overrides but preserve mode/codeTheme from base (not from overrides)
  const { mode: _m, codeTheme: _c, ...overrides } = settings.theme as Record<string, unknown>;
  return { ...base, ...overrides, name: themeName, mode: base.mode, codeTheme: base.codeTheme } as Theme;
}

function App() {
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");
  // Navigation history (browser-style back/forward)
  const historyRef = useRef<string[]>([]);
  const historyIndexRef = useRef(-1);
  const isHistoryNavRef = useRef(false);
  const [historyPos, setHistoryPos] = useState({ index: -1, length: 0 });
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [activeView, setActiveView] = useState<ActiveView>("editor");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [meetingOpen, setMeetingOpen] = useState(false);
  const [shikiTheme, setShikiTheme] = useState<[string, string]>(DEFAULT_THEME.codeTheme);
  const sidebarRef = useRef<SidebarHandle>(null);
  const sidebarPanelRef = useRef<PanelImperativeHandle>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const chatPanelRef = useRef<PanelImperativeHandle>(null);
  // Layout persistence
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: "brain-layout",
    storage: localStorage,
  });

  // Apply theme whenever settings change
  useEffect(() => {
    const theme = resolveTheme(settings);
    applyTheme(theme);
    setShikiTheme(theme.codeTheme);
    if (settings?.font_family) {
      document.documentElement.style.setProperty("--font-sans", settings.font_family);
      document.documentElement.style.setProperty("--editor-font", settings.font_family);
    } else {
      document.documentElement.style.removeProperty("--font-sans");
      document.documentElement.style.removeProperty("--editor-font");
    }
    if (settings?.editor_font_size) {
      document.documentElement.style.setProperty("--editor-font-size", `${settings.editor_font_size}px`);
    }
  }, [settings]);

  useEffect(() => {
    let settingsLoaded = false;
    async function checkConnection() {
      try {
        const h = await health();
        setConnected(true);
        setHealthStatus(h);
        const cfg = await getConfig();
        setConfig(cfg);
        // Only fetch settings once on initial connection — refreshed on save via handleCloseSettings
        if (!settingsLoaded) {
          const s = await getSettings();
          setSettings(s);
          settingsLoaded = true;
          setNeedsSetup(!s.notes_path);
        }
      } catch {
        setConnected(false);
        settingsLoaded = false;
      }
    }
    checkConnection();
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectFile = useCallback(
    async (path: string) => {
      if (!path) {
        setSelectedPath(null);
        setFileContent("");
        return;
      }
      try {
        const note = await getNoteFile(path);
        setSelectedPath(path);
        setFileContent(note.content);
        if (activeView !== "editor") setActiveView("editor");
        // Push to history unless we're navigating via back/forward
        if (!isHistoryNavRef.current) {
          const h = historyRef.current;
          const idx = historyIndexRef.current;
          // Trim forward history when navigating to a new note
          historyRef.current = [...h.slice(0, idx + 1), path];
          historyIndexRef.current = historyRef.current.length - 1;
        }
        isHistoryNavRef.current = false;
        setHistoryPos({ index: historyIndexRef.current, length: historyRef.current.length });
        // Refresh sidebar so externally-created notes (e.g. from command palette) appear
        sidebarRef.current?.refresh();
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

  const handleNavigateByTitle = useCallback(
    async (title: string) => {
      try {
        const { files } = await getNoteFiles();
        const match = files.find((f) => f.title === title);
        if (match) handleSelectFile(match.path);
      } catch (err) {
        console.error("Failed to navigate to note:", err);
      }
    },
    [handleSelectFile]
  );

  const canGoBack = historyPos.index > 0;
  const canGoForward = historyPos.index < historyPos.length - 1;

  const goBack = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
    isHistoryNavRef.current = true;
    handleSelectFile(historyRef.current[historyIndexRef.current]);
  }, [handleSelectFile]);

  const goForward = useCallback(() => {
    if (historyIndexRef.current >= historyRef.current.length - 1) return;
    historyIndexRef.current += 1;
    isHistoryNavRef.current = true;
    handleSelectFile(historyRef.current[historyIndexRef.current]);
  }, [handleSelectFile]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "f") {
        e.preventDefault();
        setActiveView("search");
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "[") {
        e.preventDefault();
        goBack();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "]") {
        e.preventDefault();
        goForward();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [goBack, goForward]);

  const handleCreateNote = useCallback(() => {
    setActiveView("editor");
    // Use setTimeout to ensure sidebar is rendered (in case we switched views)
    setTimeout(() => sidebarRef.current?.startCreating(), 0);
  }, []);
  const handleSync = useCallback(() => { syncStructural().catch(console.error); }, []);
  const handleOpenSettings = useCallback(() => { setSettingsOpen(true); }, []);

  const handleCloseSettings = useCallback(() => {
    setSettingsDirty(false);
    setSettingsOpen(false);
    getSettings().then(setSettings).catch(console.error);
  }, []);

  const handleSetupComplete = useCallback(async () => {
    setNeedsSetup(false);
    const [s, cfg] = await Promise.all([getSettings(), getConfig()]);
    setSettings(s);
    setConfig(cfg);
    sidebarRef.current?.refresh();
  }, []);

  const handleMeetingComplete = useCallback(
    (path: string) => {
      setMeetingOpen(false);
      handleSelectFile(path);
    },
    [handleSelectFile]
  );

  if (!connected) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-center">
          <p className="text-destructive mb-2">Cannot connect to Brain server</p>
          <p className="text-muted-foreground text-sm">
            Run: <code className="bg-muted px-2 py-0.5 rounded text-sm">uv run python -m brain.server</code>
          </p>
        </div>
      </div>
    );
  }

  if (needsSetup === null) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-foreground">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (needsSetup) {
    return <SetupScreen onComplete={handleSetupComplete} />;
  }

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <header className="flex items-center justify-between px-4 py-1.5 border-b border-border">
        <h1 className="text-sm font-semibold">Brain</h1>
        <div className="flex items-center gap-1 text-xs">
          {config && <span className="text-muted-foreground mr-2">{config.notes_path}</span>}
          <Button variant={activeView === "editor" ? "secondary" : "ghost"} size="sm" onClick={() => setActiveView("editor")} className="h-6 text-xs">Editor</Button>
          <Button variant={activeView === "graph" ? "secondary" : "ghost"} size="sm" onClick={() => setActiveView("graph")} className="h-6 text-xs">Graph</Button>
          <Button variant={activeView === "memory" ? "secondary" : "ghost"} size="sm" onClick={() => setActiveView("memory")} className="h-6 text-xs">Memory</Button>
          <Button variant={activeView === "search" ? "secondary" : "ghost"} size="sm" onClick={() => setActiveView("search")} className="h-6 text-xs">Search</Button>
          <div className="border-l border-border h-4 mx-1" />
          <Button variant={chatOpen ? "secondary" : "ghost"} size="sm" onClick={() => {
            const panel = chatPanelRef.current;
            if (panel) {
              if (panel.isCollapsed()) { panel.expand(); } else { panel.collapse(); }
            } else {
              setChatOpen(!chatOpen);
            }
          }} className="h-6 text-xs">Chat</Button>
          <div className="border-l border-border h-4 mx-1" />
          <Button variant={meetingOpen ? "secondary" : "ghost"} size="sm" onClick={() => setMeetingOpen(!meetingOpen)} className="h-6 w-6 p-0" title="Record Meeting">
            <MeetingIcon className="w-3.5 h-3.5" />
          </Button>
          <Button variant={settingsOpen ? "secondary" : "ghost"} size="sm" onClick={settingsOpen ? handleCloseSettings : handleOpenSettings} className="h-6 w-6 p-0" title="Settings">
            <GearIcon className="w-3.5 h-3.5" />
          </Button>
        </div>
      </header>

      {healthStatus && !healthStatus.surrealdb_connected && (
        <div className="px-4 py-1 bg-destructive/10 border-b border-destructive/20 text-xs text-destructive">
          Database not connected — agent and graph features unavailable.
        </div>
      )}

      <div className="flex-1 min-h-0 relative">
        <Group
          orientation="horizontal"
          id="brain-layout"
          defaultLayout={defaultLayout}
          onLayoutChanged={onLayoutChanged}
          style={{ height: "100%" }}
        >
          {/* Sidebar — only in editor view */}
          {activeView === "editor" && (
            <>
              <Panel id="sidebar" defaultSize="15%" minSize="8%" maxSize="30%" collapsible panelRef={sidebarPanelRef} onResize={(size) => setSidebarOpen(size.asPercentage > 0)}>
                <Sidebar ref={sidebarRef} selectedPath={selectedPath} onSelectFile={handleSelectFile} />
              </Panel>
              <Separator />
            </>
          )}

          {/* Main content */}
          <Panel id="main">
            {activeView === "editor" && (
              <Editor
                filePath={selectedPath}
                content={fileContent}
                onNavigateToNote={handleNavigateByTitle}
                keymap={settings?.editor_keymap || "vim"}
                lineNumbers={settings?.editor_line_numbers ?? false}
                wordWrap={settings?.editor_word_wrap ?? true}
                inlineFormatting={settings?.editor_inline_formatting ?? false}
                shikiTheme={shikiTheme}
                canGoBack={canGoBack}
                canGoForward={canGoForward}
                onGoBack={goBack}
                onGoForward={goForward}
                onShowSidebar={!sidebarOpen ? () => sidebarPanelRef.current?.expand() : undefined}
              />
            )}
            {activeView === "graph" && <GraphPanel onNavigateToNote={handleNavigateToNote} />}
            {activeView === "memory" && <MemoryPanel />}
            {activeView === "search" && <SearchPanel onNavigateToNote={handleNavigateToNote} />}
          </Panel>

          {/* Chat panel */}
          <Separator />
          <Panel
            id="chat"
            defaultSize="20%"
            minSize="12%"
            maxSize="40%"
            collapsible
            panelRef={chatPanelRef}
            onResize={(size) => setChatOpen(size.asPercentage > 0)}
          >
            <Chat onNavigateToNote={handleNavigateByTitle} shikiTheme={shikiTheme} />
          </Panel>
        </Group>

      </div>

      {meetingOpen && <MeetingRecorder onClose={() => setMeetingOpen(false)} onComplete={handleMeetingComplete} />}

      {settingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={handleCloseSettings} />
          <div className="relative bg-background border border-border rounded-lg shadow-xl w-full max-w-lg max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-2 border-b border-border">
              <h2 className="text-sm font-semibold">Settings</h2>
              <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-muted-foreground" onClick={handleCloseSettings}>&times;</Button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <SettingsPanel dirty={settingsDirty} setDirty={setSettingsDirty} />
            </div>
          </div>
        </div>
      )}

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onSelectNote={handleSelectFile}
        onCreateNote={handleCreateNote}
        onSwitchView={(v) => setActiveView(v as ActiveView)}
        onSync={handleSync}
        onOpenSettings={handleOpenSettings}
      />
    </div>
  );
}

export default App;
