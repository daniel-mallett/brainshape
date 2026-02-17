import time
from unittest.mock import MagicMock

from brain.watcher import NoteChangeHandler, start_watcher


class TestNoteChangeHandler:
    def test_ignores_non_markdown(self):
        callback = MagicMock()
        handler = NoteChangeHandler(callback)

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/image.png"

        handler.on_created(event)
        handler.on_modified(event)
        handler.on_deleted(event)

        # Callback should not be called (even after debounce)
        time.sleep(0.1)
        callback.assert_not_called()

    def test_ignores_directories(self):
        callback = MagicMock()
        handler = NoteChangeHandler(callback)

        event = MagicMock()
        event.is_directory = True
        event.src_path = "/notes/subfolder"

        handler.on_created(event)
        time.sleep(0.1)
        callback.assert_not_called()

    def test_fires_on_markdown_change(self):
        callback = MagicMock()
        handler = NoteChangeHandler(callback)
        handler._debounce_seconds = 0.1  # Speed up for test

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/test.md"

        handler.on_modified(event)
        time.sleep(0.3)
        callback.assert_called_once()

    def test_debounces_rapid_changes(self):
        callback = MagicMock()
        handler = NoteChangeHandler(callback)
        handler._debounce_seconds = 0.2

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/test.md"

        # Rapid fire events
        handler.on_modified(event)
        time.sleep(0.05)
        handler.on_modified(event)
        time.sleep(0.05)
        handler.on_modified(event)

        # Wait for debounce
        time.sleep(0.4)
        # Should only fire once
        callback.assert_called_once()

    def test_fires_on_deleted_markdown(self):
        callback = MagicMock()
        handler = NoteChangeHandler(callback)
        handler._debounce_seconds = 0.1

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/old.md"

        handler.on_deleted(event)
        time.sleep(0.3)
        callback.assert_called_once()

    def test_fires_on_created_markdown(self):
        callback = MagicMock()
        handler = NoteChangeHandler(callback)
        handler._debounce_seconds = 0.1

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/new.md"

        handler.on_created(event)
        time.sleep(0.3)
        callback.assert_called_once()

    def test_fire_handles_callback_error(self):
        callback = MagicMock(side_effect=RuntimeError("sync failed"))
        handler = NoteChangeHandler(callback)
        handler._debounce_seconds = 0.1

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/test.md"

        handler.on_modified(event)
        time.sleep(0.3)
        # Callback was called (and raised), but handler didn't crash
        callback.assert_called_once()
        assert handler._timer is None

    def test_fire_clears_timer_under_lock(self):
        """Regression: _fire must clear _timer inside the lock to prevent races."""
        callback = MagicMock()
        handler = NoteChangeHandler(callback)
        handler._debounce_seconds = 0.05

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/test.md"

        handler.on_modified(event)
        time.sleep(0.15)  # Wait for fire

        # Verify _timer is None (cleared inside lock)
        with handler._lock:
            assert handler._timer is None

        # Now trigger another event — should work correctly
        handler.on_modified(event)
        time.sleep(0.15)
        assert callback.call_count == 2

    def test_concurrent_fire_and_schedule(self):
        """Regression: _fire and _schedule_sync should not race on _timer."""
        import threading

        call_count = 0
        call_lock = threading.Lock()

        def slow_callback():
            nonlocal call_count
            time.sleep(0.05)
            with call_lock:
                call_count += 1

        handler = NoteChangeHandler(slow_callback)
        handler._debounce_seconds = 0.05

        event = MagicMock()
        event.is_directory = False
        event.src_path = "/notes/test.md"

        # Trigger an event, let it fire, then immediately trigger another
        handler.on_modified(event)
        time.sleep(0.08)  # Timer fires, callback starts
        handler.on_modified(event)  # Schedule new while old callback runs
        time.sleep(0.2)

        # Both callbacks should have completed without errors
        with call_lock:
            assert call_count == 2


class TestStartWatcher:
    def test_starts_and_stops(self, tmp_path):
        callback = MagicMock()
        observer = start_watcher(tmp_path, callback)
        assert observer.is_alive()
        observer.stop()
        observer.join(timeout=2)
        assert not observer.is_alive()
