import sys
from unittest.mock import MagicMock

import pytest

from brain.transcribe import _get_model_path, reset_model, transcribe_audio


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


def test_transcribe_audio(mock_mlx_whisper, tmp_path, monkeypatch):
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"fake audio data")

    monkeypatch.setattr("brain.transcribe._get_model_path", lambda: "test-model")

    mock_mlx_whisper.transcribe.return_value = {
        "text": " Hello, this is a test. ",
        "segments": [
            {"start": 0.0, "end": 2.5, "text": " Hello, this is a test. "},
        ],
    }

    result = transcribe_audio(str(audio_file))

    assert result["text"] == "Hello, this is a test."
    assert len(result["segments"]) == 1
    assert result["segments"][0]["start"] == 0.0
    assert result["segments"][0]["text"] == "Hello, this is a test."

    mock_mlx_whisper.transcribe.assert_called_once_with(
        str(audio_file),
        path_or_hf_repo="test-model",
        language="en",
        word_timestamps=True,
    )


def test_get_model_path_default(monkeypatch, tmp_path):
    """Uses default model when settings has no whisper_model."""
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
    path = _get_model_path()
    assert path == "mlx-community/whisper-small"


def test_get_model_path_custom(monkeypatch, tmp_path):
    """Uses custom model from settings."""
    import json

    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"whisper_model": "custom/model"}))

    path = _get_model_path()
    assert path == "custom/model"


def test_get_model_path_caches(monkeypatch, tmp_path):
    """Caches result after first call."""
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
    path1 = _get_model_path()
    # Even if settings change, cached value is returned
    import json

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"whisper_model": "changed/model"}))
    path2 = _get_model_path()
    assert path1 == path2  # cached


def test_transcribe_empty_segments(mock_mlx_whisper, tmp_path, monkeypatch):
    audio_file = tmp_path / "test.wav"
    audio_file.write_bytes(b"fake")

    monkeypatch.setattr("brain.transcribe._get_model_path", lambda: "test-model")

    mock_mlx_whisper.transcribe.return_value = {
        "text": "Just text",
    }

    result = transcribe_audio(str(audio_file))
    assert result["text"] == "Just text"
    assert result["segments"] == []
