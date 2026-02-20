"""Voice transcription with pluggable providers.

Supports local (mlx-whisper on Apple Silicon), OpenAI Whisper API,
and Mistral Voxtral API. Provider selection is settings-driven.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy-loaded local model reference
_local_model_path: str | None = None


def _get_model(settings: dict) -> str:
    """Resolve the transcription model, falling back to provider default."""
    from brainshape.settings import TRANSCRIPTION_MODEL_DEFAULTS

    model = settings.get("transcription_model", "")
    if model:
        return model
    provider = settings.get("transcription_provider", "local")
    return TRANSCRIPTION_MODEL_DEFAULTS.get(provider, "mlx-community/whisper-small")


def _transcribe_local(audio_path: str | Path, settings: dict) -> dict:
    """Transcribe using local mlx-whisper (Apple Silicon only)."""
    global _local_model_path

    try:
        import mlx_whisper  # type: ignore[unresolved-import]
    except ImportError:
        raise RuntimeError(
            "Local transcription requires mlx-whisper (Apple Silicon only). "
            "Install it with `uv add mlx-whisper`, or switch to a cloud "
            "provider (OpenAI or Mistral) in Settings > Voice Transcription."
        ) from None

    model_path = _get_model(settings)
    _local_model_path = model_path
    logger.info("Transcribing %s with local model %s", audio_path, model_path)

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


def _transcribe_openai(audio_path: str | Path, settings: dict) -> dict:
    """Transcribe using OpenAI Whisper API."""
    import httpx

    api_key = settings.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OpenAI transcription requires an API key. Set it in Settings or export OPENAI_API_KEY."
        )

    model = _get_model(settings)
    logger.info("Transcribing %s with OpenAI model %s", audio_path, model)

    try:
        with Path(audio_path).open("rb") as f:
            response = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (Path(audio_path).name, f)},
                data={"model": model, "response_format": "verbose_json"},
                timeout=300,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"OpenAI API error ({e.response.status_code}): {e.response.text[:200]}"
        ) from None

    data = response.json()
    return {
        "text": data.get("text", "").strip(),
        "segments": [
            {
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", "").strip(),
            }
            for seg in data.get("segments", [])
        ],
    }


def _transcribe_mistral(audio_path: str | Path, settings: dict) -> dict:
    """Transcribe using Mistral Voxtral API."""
    import httpx

    api_key = settings.get("mistral_api_key") or os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "Mistral transcription requires an API key. "
            "Set it in Settings or export MISTRAL_API_KEY."
        )

    model = _get_model(settings)
    logger.info("Transcribing %s with Mistral model %s", audio_path, model)

    try:
        with Path(audio_path).open("rb") as f:
            response = httpx.post(
                "https://api.mistral.ai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (Path(audio_path).name, f)},
                data={
                    "model": model,
                    "timestamp_granularities": "segment",
                },
                timeout=300,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"Mistral API error ({e.response.status_code}): {e.response.text[:200]}"
        ) from None

    data = response.json()
    segments = data.get("segments", [])
    return {
        "text": data.get("text", "").strip(),
        "segments": [
            {
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", "").strip(),
            }
            for seg in segments
        ],
    }


_PROVIDERS = {
    "local": _transcribe_local,
    "openai": _transcribe_openai,
    "mistral": _transcribe_mistral,
}


def transcribe_audio(audio_path: str | Path) -> dict:
    """Transcribe an audio file using the configured provider.

    Args:
        audio_path: Path to the audio file (wav, mp3, m4a, webm, etc.)

    Returns:
        Dict with 'text' (full transcription) and 'segments'
        (list of {start, end, text} timestamped chunks).
    """
    from brainshape.settings import load_settings

    settings = load_settings()
    provider = settings.get("transcription_provider", "local")

    fn = _PROVIDERS.get(provider)
    if not fn:
        raise ValueError(
            f"Unknown transcription provider: {provider!r}. Valid: {', '.join(sorted(_PROVIDERS))}"
        )
    return fn(audio_path, settings)


def reset_model():
    """Reset the cached local model path (e.g. after settings change)."""
    global _local_model_path
    _local_model_path = None
