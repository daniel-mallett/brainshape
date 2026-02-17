"""Batch sync entry point for cron/launchd jobs.

Usage:
    uv run python -m brainshape.batch                  # semantic only (default)
    uv run python -m brainshape.batch --structural     # structural only
    uv run python -m brainshape.batch --full           # structural + semantic

Only processes dirty files (content hash comparison).

Example cron (overnight semantic processing):
    0 3 * * * cd /path/to/brainshape && uv run python -m brainshape.batch
"""

import argparse
import sys
from pathlib import Path

from brainshape.graph_db import GraphDB
from brainshape.kg_pipeline import create_kg_pipeline
from brainshape.sync import sync_all, sync_semantic, sync_structural


def main():
    parser = argparse.ArgumentParser(description="Brainshape notes sync (batch mode)")
    parser.add_argument("--structural", action="store_true", help="Run structural sync only")
    parser.add_argument("--full", action="store_true", help="Run structural + semantic sync")
    args = parser.parse_args()

    from brainshape.settings import get_notes_path

    notes_path = Path(get_notes_path()).expanduser()
    if not notes_path.exists():
        print(f"Error: notes path {notes_path} does not exist", file=sys.stderr)
        sys.exit(1)

    db = GraphDB()
    db.bootstrap_schema()

    try:
        if args.structural:
            stats = sync_structural(db, notes_path)
            print(
                f"Structural: {stats['notes']} notes, "
                f"{stats['tags']} tag links, {stats['links']} note links"
            )
        elif args.full:
            pipeline = create_kg_pipeline(db, notes_path)
            stats = sync_all(db, pipeline, notes_path)
            s, sem = stats["structural"], stats["semantic"]
            print(f"Structural: {s['notes']} notes, {s['tags']} tag links, {s['links']} note links")
            print(f"Semantic: {sem['processed']} processed, {sem['skipped']} skipped")
        else:
            # Default: semantic only (the expensive/important one for overnight batch)
            pipeline = create_kg_pipeline(db, notes_path)
            stats = sync_semantic(db, pipeline, notes_path)
            print(f"Semantic: {stats['processed']} processed, {stats['skipped']} skipped")
    finally:
        db.close()


if __name__ == "__main__":
    main()
