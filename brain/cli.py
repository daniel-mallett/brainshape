import sys
from pathlib import Path

from brain.agent import create_brain_agent
from brain.config import settings
from brain.sync import sync_structural


def run_cli():
    print("Starting Brain...")
    agent, db, pipeline = create_brain_agent()

    # Sync vault on startup (structural only — semantic is expensive)
    vault_path = Path(settings.vault_path).expanduser()
    if vault_path.exists():
        notes = list(vault_path.rglob("*.md"))
        if notes:
            print(f"Syncing vault from {vault_path} ({len(notes)} notes)...")
            stats = sync_structural(db, vault_path)
            print(
                f"  Synced {stats['notes']} notes, "
                f"{stats['tags']} tag links, "
                f"{stats['links']} note links"
            )
        else:
            print(f"Vault at {vault_path} is empty.")
    else:
        print(f"Vault path {vault_path} not found. Starting without vault sync.")
        print(f"  Create it with: mkdir -p {vault_path}")

    print("\nBrain is ready. Type 'quit' or 'exit' to stop.\n")

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

        messages = {"messages": [{"role": "user", "content": user_input}]}
        print("Brain: ", end="", flush=True)

        try:
            for chunk in agent.stream(messages, config=config, stream_mode="updates"):
                if "agent" in chunk:
                    for msg in chunk["agent"]["messages"]:
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
