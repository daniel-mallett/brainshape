import sys
from pathlib import Path

from brain.agent import create_brain_agent
from brain.config import settings
from brain.graph_db import GraphDB
from brain.kg_pipeline import KGPipeline
from brain.sync import sync_semantic, sync_structural, sync_vault


def _run_sync(db: GraphDB, pipeline: KGPipeline, args: list[str]) -> None:
    vault_path = Path(settings.vault_path).expanduser()
    if not vault_path.exists():
        print(f"Vault path {vault_path} not found.")
        return

    if "--full" in args:
        print("Running full sync (structural + semantic, incremental)...")
        stats = sync_vault(db, pipeline, vault_path)
        s = stats["structural"]
        sem = stats["semantic"]
        print(
            f"  Structural: {s['notes']} notes, "
            f"{s['tags']} tag links, {s['links']} note links"
        )
        print(f"  Semantic: {sem['processed']} processed, {sem['skipped']} skipped")
    elif "--semantic" in args:
        print("Running semantic sync (incremental)...")
        stats = sync_semantic(db, pipeline, vault_path)
        print(f"  Processed: {stats['processed']}, Skipped: {stats['skipped']}")
    else:
        print("Running structural sync...")
        stats = sync_structural(db, vault_path)
        print(
            f"  {stats['notes']} notes, "
            f"{stats['tags']} tag links, {stats['links']} note links"
        )


def _handle_command(command: str, db: GraphDB, pipeline: KGPipeline) -> None:
    parts = command.strip().split()
    cmd = parts[0].lower()

    if cmd == "/sync":
        _run_sync(db, pipeline, parts[1:])
    elif cmd == "/help":
        print("Commands:")
        print("  /sync              — Structural sync (fast, incremental)")
        print("  /sync --full       — Full sync: structural + semantic (incremental)")
        print("  /sync --semantic   — Semantic sync only (incremental)")
        print("  /help              — Show this help")
        print("  quit / exit        — Exit Brain")
    else:
        print(f"Unknown command: {cmd}. Type /help for available commands.")


def run_cli():
    print("Starting Brain...")
    agent, db, pipeline = create_brain_agent()

    # Structural sync on startup
    vault_path = Path(settings.vault_path).expanduser()
    if vault_path.exists():
        notes = list(vault_path.rglob("*.md"))
        if notes:
            print(f"Syncing vault from {vault_path} ({len(notes)} notes)...")
            stats = sync_structural(db, vault_path)
            print(
                f"  {stats['notes']} notes, "
                f"{stats['tags']} tag links, {stats['links']} note links"
            )
        else:
            print(f"Vault at {vault_path} is empty.")
    else:
        print(f"Vault path {vault_path} not found. Starting without vault sync.")
        print(f"  Create it with: mkdir -p {vault_path}")

    print("\nBrain is ready. Type 'quit' or 'exit' to stop. Type /help for commands.\n")

    thread_id = "cli-session"
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        # Handle slash commands
        if user_input.startswith("/"):
            _handle_command(user_input, db, pipeline)
            continue

        messages = {"messages": [{"role": "user", "content": user_input}]}
        print("Brain: ", end="", flush=True)

        try:
            for chunk in agent.stream(messages, config=config, stream_mode="updates"):
                node = chunk.get("model") or chunk.get("agent")
                if node:
                    for msg in node["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            # Skip tool call messages
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                continue
                            if isinstance(msg.content, str):
                                print(msg.content, end="", flush=True)
                            elif isinstance(msg.content, list):
                                for block in msg.content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        print(block["text"], end="", flush=True)
                                    elif isinstance(block, str):
                                        print(block, end="", flush=True)
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)

        print()

    db.close()
