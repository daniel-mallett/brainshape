import sys
from unittest.mock import MagicMock

import pytest

from brain.transcribe import reset_model, transcribe_audio


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
