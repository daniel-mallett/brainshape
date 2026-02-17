import { useEffect, useState } from "react";
import { useVoiceRecorder } from "../lib/useVoiceRecorder";
import { transcribeMeeting } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

interface MeetingRecorderProps {
  onClose: () => void;
  onComplete: (path: string) => void;
}

export function MeetingRecorder({ onClose, onComplete }: MeetingRecorderProps) {
  const { duration, startRecording, stopRecording, cancelRecording } =
    useVoiceRecorder();

  // Release microphone if component unmounts while recording
  useEffect(() => cancelRecording, [cancelRecording]);
  const [phase, setPhase] = useState<"idle" | "recording" | "details" | "transcribing">("idle");
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [title, setTitle] = useState("");
  const [folder, setFolder] = useState("");
  const [tags, setTags] = useState("");
  const [error, setError] = useState<string | null>(null);

  const formatDuration = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handleStartRecording = async () => {
    setError(null);
    try {
      await startRecording();
      setPhase("recording");
    } catch {
      setError("Microphone access denied");
    }
  };

  const handleStopRecording = async () => {
    const blob = await stopRecording();
    if (blob.size === 0) {
      setError("No audio recorded");
      setPhase("idle");
      return;
    }
    setAudioBlob(blob);
    // Auto-generate title
    const now = new Date();
    setTitle(`Meeting ${now.toLocaleDateString()} ${now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
    setPhase("details");
  };

  const handleSubmit = async () => {
    if (!audioBlob) return;
    setPhase("transcribing");
    setError(null);
    try {
      const result = await transcribeMeeting(audioBlob, title, folder, tags);
      onComplete(result.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transcription failed");
      setPhase("details");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={phase !== "transcribing" ? onClose : undefined} />
      <div className="relative bg-background border border-border rounded-lg shadow-xl w-full max-w-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Record Meeting</h2>
          {phase !== "transcribing" && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 w-6 p-0 text-muted-foreground"
              onClick={onClose}
              aria-label="Close"
            >
              &times;
            </Button>
          )}
        </div>

        {/* Idle — start recording */}
        {phase === "idle" && (
          <div className="text-center space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Record audio and Brain will create a timestamped meeting note.
            </p>
            <Button onClick={handleStartRecording} className="w-full">
              Start Recording
            </Button>
          </div>
        )}

        {/* Recording */}
        {phase === "recording" && (
          <div className="text-center space-y-4 py-4">
            <div className="flex items-center justify-center gap-3">
              <span className="inline-block w-3 h-3 rounded-full bg-red-500 animate-pulse" />
              <span className="text-2xl font-mono tabular-nums">
                {formatDuration(duration)}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">Recording...</p>
            <Button variant="destructive" onClick={handleStopRecording} className="w-full">
              Stop Recording
            </Button>
          </div>
        )}

        {/* Details form */}
        {phase === "details" && (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Title</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Meeting title..."
                className="h-8 text-sm"
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Folder</label>
              <Input
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder="Optional subfolder..."
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Tags</label>
              <Input
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="meeting, project (comma-separated)"
                className="h-8 text-sm"
              />
            </div>
            <Button onClick={handleSubmit} className="w-full">
              Transcribe & Create Note
            </Button>
          </div>
        )}

        {/* Transcribing */}
        {phase === "transcribing" && (
          <div className="text-center space-y-3 py-4">
            <div className="animate-spin w-6 h-6 border-2 border-muted-foreground border-t-foreground rounded-full mx-auto" />
            <p className="text-sm text-muted-foreground">Transcribing audio...</p>
          </div>
        )}

        {error && (
          <p className="text-xs text-destructive text-center">{error}</p>
        )}
      </div>
    </div>
  );
}
