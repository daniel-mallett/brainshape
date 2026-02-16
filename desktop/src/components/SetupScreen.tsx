import { useState } from "react";
import { updateSettings } from "../lib/api";
import { isTauri, pickDirectory } from "../lib/tauri";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

interface SetupScreenProps {
  onComplete: (notesPath: string) => void;
}

export function SetupScreen({ onComplete }: SetupScreenProps) {
  const [path, setPath] = useState("~/brain");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleContinue = async () => {
    if (!path.trim()) return;
    setSaving(true);
    setError("");
    try {
      await updateSettings({ notes_path: path.trim() });
      onComplete(path.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleBrowse = async () => {
    const dir = await pickDirectory("Choose your notes directory");
    if (dir) setPath(dir);
  };

  return (
    <div className="h-screen flex items-center justify-center bg-background text-foreground">
      <div className="max-w-md w-full p-8 space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold">Welcome to Brain</h1>
          <p className="text-muted-foreground text-sm">
            Choose a directory for your notes. This is where your markdown
            files will be stored.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Notes Directory</label>
          <div className="flex gap-2">
            <Input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="~/brain"
              className="flex-1"
            />
            {isTauri() && (
              <Button variant="outline" onClick={handleBrowse}>
                Browse
              </Button>
            )}
          </div>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button
          className="w-full"
          onClick={handleContinue}
          disabled={saving || !path.trim()}
        >
          {saving ? "Setting up..." : "Get Started"}
        </Button>
      </div>
    </div>
  );
}
