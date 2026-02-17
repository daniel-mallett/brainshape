"""File watcher for auto-syncing notes to the knowledge graph.

Uses watchdog to monitor the notes directory and trigger structural + semantic
sync when markdown files are created, modified, or deleted.
"""

import logging
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class NoteChangeHandler(FileSystemEventHandler):
    """Debounced handler that triggers sync on .md file changes."""

    def __init__(self, on_change: Callable[[], None]):
        super().__init__()
        self._on_change = on_change
        self._timer = None
        self._debounce_seconds = 2.0
        self._lock = __import__("threading").Lock()

    def _is_markdown(self, path: str | bytes) -> bool:
        if isinstance(path, bytes):
            return path.endswith(b".md")
        return path.endswith(".md")

    def _schedule_sync(self) -> None:
        """Debounce: reset timer on each event, fire after quiet period."""
        import threading

        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_seconds, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        self._timer = None
        try:
            self._on_change()
        except Exception:
            logger.exception("Error during auto-sync")

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_markdown(event.src_path):
            logger.info("Note created: %s", event.src_path)
            self._schedule_sync()

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_markdown(event.src_path):
            logger.info("Note modified: %s", event.src_path)
            self._schedule_sync()

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory and self._is_markdown(event.src_path):
            logger.info("Note deleted: %s", event.src_path)
            self._schedule_sync()


def start_watcher(notes_path: Path, on_change: Callable[[], None]) -> Observer:  # type: ignore[invalid-type-form]
    """Start watching the notes directory for .md changes.

    Returns the Observer instance (call .stop() to shut down).
    """
    handler = NoteChangeHandler(on_change)
    observer = Observer()
    observer.schedule(handler, str(notes_path), recursive=True)
    observer.daemon = True
    observer.start()
    logger.info("Watching %s for note changes", notes_path)
    return observer
