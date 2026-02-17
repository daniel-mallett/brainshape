import sys
from unittest.mock import MagicMock, patch

import pytest

from brainshape.transcribe import (
    _get_model,
    _transcribe_local,
    _transcribe_mistral,
    _transcribe_openai,
    reset_model,
    transcribe_audio,
)


@pytest.fixture(autouse=True)
def reset():
    """Reset cached model path between tests."""
    reset_model()
    yield
    reset_model()


@pytest.fixture(autouse=True)
def mock_mlx_whisper():
    """Mock mlx_whisper module since it may not be installed in test env."""
    mock = MagicMock()
    sys.modules["mlx_whisper"] = mock
    yield mock
    sys.modules.pop("mlx_whisper", None)


# --- _get_model ---


def test_get_model_uses_explicit_setting():
    settings = {"transcription_provider": "openai", "transcription_model": "whisper-1"}
    assert _get_model(settings) == "whisper-1"


def test_get_model_falls_back_to_provider_default():
    settings = {"transcription_provider": "openai", "transcription_model": ""}
    assert _get_model(settings) == "gpt-4o-mini-transcribe"


def test_get_model_local_default():
    settings = {"transcription_provider": "local", "transcription_model": ""}
    assert _get_model(settings) == "mlx-community/whisper-small"


def test_get_model_mistral_default():
    settings = {"transcription_provider": "mistral", "transcription_model": ""}
    assert _get_model(settings) == "voxtral-mini-latest"


# --- Provider dispatch ---


def test_transcribe_audio_dispatches_to_local(mock_mlx_whisper, tmp_path, monkeypatch):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")

    mock_mlx_whisper.transcribe.return_value = {
        "text": " Hello ",
        "segments": [{"start": 0.0, "end": 1.0, "text": " Hello "}],
    }
    monkeypatch.setattr("brainshape.settings.SETTINGS_FILE", tmp_path / "settings.json")

    result = transcribe_audio(str(audio))
    assert result["text"] == "Hello"
    assert len(result["segments"]) == 1


def test_transcribe_audio_unknown_provider(monkeypatch, tmp_path):
    import json

    monkeypatch.setattr("brainshape.settings.SETTINGS_FILE", tmp_path / "settings.json")
    sf = tmp_path / "settings.json"
    sf.write_text(json.dumps({"transcription_provider": "nonexistent"}))

    with pytest.raises(ValueError, match="Unknown transcription provider"):
        transcribe_audio("/fake/path.wav")


# --- Local provider ---


def test_local_transcription(mock_mlx_whisper, tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")

    mock_mlx_whisper.transcribe.return_value = {
        "text": " Test result. ",
        "segments": [{"start": 0.0, "end": 2.5, "text": " Test result. "}],
    }

    settings = {"transcription_provider": "local", "transcription_model": ""}
    result = _transcribe_local(str(audio), settings)

    assert result["text"] == "Test result."
    assert result["segments"][0]["start"] == 0.0
    mock_mlx_whisper.transcribe.assert_called_once_with(
        str(audio),
        path_or_hf_repo="mlx-community/whisper-small",
        language="en",
        word_timestamps=True,
    )


def test_local_import_error(tmp_path):
    """Clear error when mlx_whisper not available."""
    sys.modules.pop("mlx_whisper", None)
    # Temporarily make import fail
    sys.modules["mlx_whisper"] = None  # type: ignore[assignment]

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")

    with pytest.raises(RuntimeError, match="Apple Silicon"):
        _transcribe_local(
            str(audio),
            {"transcription_provider": "local", "transcription_model": ""},
        )

    # Restore mock
    sys.modules.pop("mlx_whisper", None)


def test_local_empty_segments(mock_mlx_whisper, tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")

    mock_mlx_whisper.transcribe.return_value = {"text": "Just text"}

    settings = {"transcription_provider": "local", "transcription_model": ""}
    result = _transcribe_local(str(audio), settings)
    assert result["text"] == "Just text"
    assert result["segments"] == []


# --- OpenAI provider ---


def test_openai_transcription(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "text": "Hello world",
        "segments": [{"start": 0.0, "end": 1.5, "text": "Hello world"}],
    }
    mock_response.raise_for_status = MagicMock()

    settings = {
        "transcription_provider": "openai",
        "transcription_model": "",
        "openai_api_key": "sk-test",
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = _transcribe_openai(str(audio), settings)

    assert result["text"] == "Hello world"
    assert len(result["segments"]) == 1
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "api.openai.com" in call_kwargs.args[0]


def test_openai_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")

    with pytest.raises(RuntimeError, match="OpenAI transcription requires"):
        _transcribe_openai(
            str(audio),
            {"transcription_provider": "openai", "transcription_model": "", "openai_api_key": ""},
        )


# --- Mistral provider ---


def test_mistral_transcription(tmp_path):
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "text": "Bonjour",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Bonjour"}],
    }
    mock_response.raise_for_status = MagicMock()

    settings = {
        "transcription_provider": "mistral",
        "transcription_model": "",
        "mistral_api_key": "mk-test",
    }

    with patch("httpx.post", return_value=mock_response) as mock_post:
        result = _transcribe_mistral(str(audio), settings)

    assert result["text"] == "Bonjour"
    assert len(result["segments"]) == 1
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "api.mistral.ai" in call_kwargs.args[0]


def test_mistral_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake")

    with pytest.raises(RuntimeError, match="Mistral transcription requires"):
        _transcribe_mistral(
            str(audio),
            {"transcription_provider": "mistral", "transcription_model": "", "mistral_api_key": ""},
        )


# --- HTTP error handling ---


def test_openai_http_error(tmp_path):
    """OpenAI API errors should surface as RuntimeError with status code."""
    import httpx

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid API key"
    error = httpx.HTTPStatusError("err", request=MagicMock(), response=mock_response)

    settings = {
        "transcription_provider": "openai",
        "transcription_model": "",
        "openai_api_key": "sk-bad",
    }

    with (
        patch("httpx.post", side_effect=error),
        pytest.raises(RuntimeError, match="OpenAI API error.*401"),
    ):
        _transcribe_openai(str(audio), settings)


def test_mistral_http_error(tmp_path):
    """Mistral API errors should surface as RuntimeError with status code."""
    import httpx

    audio = tmp_path / "test.wav"
    audio.write_bytes(b"fake audio")

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"
    error = httpx.HTTPStatusError("err", request=MagicMock(), response=mock_response)

    settings = {
        "transcription_provider": "mistral",
        "transcription_model": "",
        "mistral_api_key": "mk-bad",
    }

    with (
        patch("httpx.post", side_effect=error),
        pytest.raises(RuntimeError, match="Mistral API error.*429"),
    ):
        _transcribe_mistral(str(audio), settings)
