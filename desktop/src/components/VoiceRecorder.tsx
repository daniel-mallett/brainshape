import { useEffect, useState } from "react";
import { useVoiceRecorder } from "../lib/useVoiceRecorder";
import { transcribeAudio, type Settings } from "../lib/api";
import { Button } from "./ui/button";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
  disabled?: boolean;
  settings: Settings | null;
  onOpenSettings: () => void;
}

/** Check if transcription is ready. Returns an error message or null. */
function checkTranscriptionReady(settings: Settings | null): string | null {
  if (!settings) return "Settings not loaded.";
  const provider = settings.transcription_provider || "local";
  if (provider === "local") return "Voice transcription not configured. Set it up in Settings.";
  if (provider === "openai" && !settings.openai_api_key_set) return "OpenAI API key required. Set it up in Settings.";
  if (provider === "mistral" && !settings.mistral_api_key_set) return "Mistral API key required. Set it up in Settings.";
  return null;
}

export function VoiceRecorder({ onTranscription, disabled, settings, onOpenSettings }: VoiceRecorderProps) {
  const { isRecording, duration, startRecording, stopRecording, cancelRecording } =
    useVoiceRecorder();

  // Release microphone if component unmounts while recording
  useEffect(() => cancelRecording, [cancelRecording]);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const configError = checkTranscriptionReady(settings);

  const handleClick = async () => {
    setError(null);

    // Block recording if transcription isn't configured
    if (!isRecording && configError) {
      setError(configError);
      onOpenSettings();
      return;
    }

    if (isRecording) {
      const blob = await stopRecording();
      if (blob.size === 0) return;

      setTranscribing(true);
      try {
        const result = await transcribeAudio(blob);
        if (result.text) {
          onTranscription(result.text);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Transcription failed");
      } finally {
        setTranscribing(false);
      }
    } else {
      try {
        await startRecording();
      } catch {
        setError("Microphone access denied");
      }
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      <Button
        type="button"
        variant={isRecording ? "destructive" : "ghost"}
        size="sm"
        onClick={handleClick}
        disabled={disabled || transcribing}
        className="h-8 px-2"
        title={isRecording ? "Stop recording" : configError || "Start voice recording"}
        aria-label={isRecording ? "Stop recording" : "Start voice recording"}
      >
        {transcribing ? (
          <span className="text-xs">Transcribing...</span>
        ) : isRecording ? (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-full bg-red-400 animate-pulse" />
            <span className="text-xs">{formatDuration(duration)}</span>
          </span>
        ) : (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
        )}
      </Button>
      {error && (
        <span className="text-xs text-destructive">{error}</span>
      )}
    </div>
  );
}
