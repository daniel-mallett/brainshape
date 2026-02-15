"""Local voice transcription using mlx-whisper.

Runs Whisper large-v3-turbo on Apple Silicon via MLX. Fully offline —
no network calls, no API keys. Audio goes in, text comes out.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded model reference
_model_path: str | None = None


def _get_model_path() -> str:
    """Get the configured Whisper model path."""
    global _model_path
    if _model_path is None:
        from brain.settings import load_settings

        settings = load_settings()
        _model_path = settings.get("whisper_model", "mlx-community/whisper-large-v3-turbo")
    return _model_path


def transcribe_audio(audio_path: str | Path) -> dict:
    """Transcribe an audio file using mlx-whisper.

    Args:
        audio_path: Path to the audio file (wav, mp3, m4a, etc.)

    Returns:
        Dict with 'text' (full transcription) and 'segments' (timestamped chunks).
    """
    import mlx_whisper

    model_path = _get_model_path()
    logger.info("Transcribing %s with model %s", audio_path, model_path)

    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=model_path,
        language="en",
        word_timestamps=True,
    )

    return {
        "text": result["text"].strip(),
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ],
    }


def reset_model():
    """Reset the cached model path (e.g. after settings change)."""
    global _model_path
    _model_path = None
