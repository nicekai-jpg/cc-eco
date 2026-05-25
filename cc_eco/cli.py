"""CLI entry point for cc-eco."""

import argparse
import json
import sys
from pathlib import Path

from cc_eco import __version__
from cc_eco.db import (
    save_db_state,
    restore_db_state,
    regenerate_settings,
    get_enabled_skill_names,
    get_disabled_skill_names,
)
from cc_eco.fs import (
    init_isolation,
    copy_snapshot,
    switch_symlinks,
    sync_skills_symlinks,
    adopt_path,
    discover_paths,
    delete_ecosystem,
    create_eco_json,
)
from cc_eco.platform_restart import restart_processes
from cc_eco.utils import (
    ECO_DIR,
    CURRENT_FILE,
    ISOLATION_FILE,
    DB_PATH,
    CLAUDE_DIR,
    SKILLS_DIR,
    require_init,
    get_current,
    set_current,
    get_isolation_items,
    backup_db,
    eco_dir,
    db_state_file,
    eco_json_file,
    load_db_state,
    load_eco_json,
    info,
    warn,
    error,
    step,
    heading,
    confirm,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cc-eco",
        description="Claude Code ecosystem switcher",
    )
    parser.add_argument("--version", action="version", version=f"cc-eco {__version__}")

    sub = parser.add_subparsers(dest="command")

    # init
    p = sub.add_parser("init", help="Initialize cc-eco and save current state as first ecosystem")
    p.add_argument("name", help="Name for the initial ecosystem")

    # snapshot
    p = sub.add_parser("snapshot", help="Create a new ecosystem snapshot from current state")
    p.add_argument("name", help="Name for the new snapshot")

    # switch
    p = sub.add_parser("switch", help="Switch to a different ecosystem")
    p.add_argument("name", help="Name of the ecosystem to switch to")
    p.add_argument("--no-restart", action="store_true", help="Don't restart processes after switch")

    # status
    sub.add_parser("status", help="Show current ecosystem status")

    # list
    sub.add_parser("list", help="List all ecosystems")

    # delete
    p = sub.add_parser("delete", help="Delete an ecosystem")
    p.add_argument("name", help="Name of the ecosystem to delete")
    p.add_argument("--force", action="store_true", help="Skip confirmation")

    # discover
    sub.add_parser("discover", help="Find paths that might need isolation")

    # adopt
    p = sub.add_parser("adopt", help="Add a path to isolation")
    p.add_argument("path", help="Path relative to ~/.claude/ to adopt")

    # isolate
    sub.add_parser("isolate", help="Show isolated paths")

    return parser


# ─── Command implementations ────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> None:
    name = args.name
    heading(f"Initializing cc-eco with ecosystem '{name}'")

    if ECO_DIR.exists() and any(ECO_DIR.iterdir()):
        if CURRENT_FILE.exists():
            error("cc-eco is already initialized")
            sys.exit(1)

    ECO_DIR.mkdir(parents=True, exist_ok=True)

    # Default isolation items
    default_items = ["skills", "commands"]
    ISOLATION_FILE.write_text("\n".join(default_items) + "\n")
    info(f"Default isolation items: {', '.join(default_items)}")

    # Create ecosystem directory
    eco_path = eco_dir(name)
    eco_path.mkdir(parents=True, exist_ok=True)

    # Save DB state
    save_db_state(name, eco_path)

    # Set up file-level isolation
    init_isolation(name)

    # Set current
    set_current(name)

    info(f"Initialized ecosystem '{name}'")


def cmd_snapshot(args: argparse.Namespace) -> None:
    name = args.name
    require_init()

    current = get_current()
    if not current:
        error("No current ecosystem set")
        sys.exit(1)

    heading(f"Creating snapshot '{name}' from '{current}'")

    if eco_dir(name).exists():
        error(f"Ecosystem '{name}' already exists")
        sys.exit(1)

    # Copy current ecosystem directory
    copy_snapshot(current, name)

    # Save current DB state into the new snapshot
    save_db_state(name, eco_dir(name))

    info(f"Snapshot '{name}' created")


def cmd_switch(args: argparse.Namespace) -> None:
    name = args.name
    require_init()

    current = get_current()
    if current == name:
        warn(f"Already on ecosystem '{name}'")
        return

    if not eco_dir(name).exists():
        error(f"Ecosystem '{name}' does not exist")
        sys.exit(1)

    heading(f"Switching to ecosystem '{name}'")

    # Phase 1: Save current state
    if current:
        step(f"Saving current state of '{current}'")
        save_db_state(current, eco_dir(current))

    # Phase 2: Backup DB
    step("Backing up database")
    backup_db()

    # Phase 3: Restore target state
    step(f"Restoring state of '{name}'")
    state = restore_db_state(name, eco_dir(name))

    # Phase 4: Switch file-level symlinks
    step("Switching symlinks")
    switch_symlinks(name)

    # Phase 5: Sync skill symlinks
    step("Syncing skill symlinks")
    sync_skills_symlinks(name)

    # Phase 6: Regenerate settings.json
    step("Regenerating settings.json")
    regenerate_settings()

    # Update current
    set_current(name)

    # Phase 7: Restart processes
    restart_processes(no_restart=args.no_restart)


def cmd_status(args: argparse.Namespace) -> None:
    require_init()

    current = get_current()
    if current:
        info(f"Current ecosystem: {current}")
    else:
        warn("No current ecosystem set")

    # Show eco.json details
    if current:
        eco_data = load_eco_json(current)
        if eco_data:
            print(f"  Description: {eco_data.get('description', '(none)')}")
            plugins = eco_data.get("enabled_plugins", [])
            if plugins:
                print(f"  Plugins: {', '.join(plugins)}")
            repos = eco_data.get("skill_repos", [])
            if repos:
                print(f"  Skill repos: {', '.join(repos)}")

    # Show DB state info
    if current:
        state = load_db_state(current)
        if state:
            skills = state.get("skills", {})
            enabled = sum(1 for v in skills.values() if v.get("enabled_claude") == 1)
            disabled = sum(1 for v in skills.values() if v.get("enabled_claude") == 0)
            mcps = state.get("mcp_servers", {})
            mcp_enabled = sum(1 for v in mcps.values() if v.get("enabled_claude") == 1)
            print(f"  Skills: {enabled} enabled, {disabled} disabled")
            print(f"  MCP servers: {mcp_enabled} enabled")

    # Show isolation items
    items = get_isolation_items()
    if items:
        print(f"  Isolated paths: {', '.join(items)}")


def cmd_list(args: argparse.Namespace) -> None:
    require_init()

    current = get_current()
    ecosystems = sorted(
        entry.name
        for entry in ECO_DIR.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )

    if not ecosystems:
        warn("No ecosystems found")
        return

    heading("Ecosystems")
    for name in ecosystems:
        marker = " ← current" if name == current else ""
        eco_data = load_eco_json(name)
        desc = eco_data.get("description", "") if eco_data else ""
        line = f"  {name}{marker}"
        if desc:
            line += f"  — {desc}"
        print(line)


def cmd_delete(args: argparse.Namespace) -> None:
    name = args.name
    require_init()

    current = get_current()
    if name == current:
        error(f"Cannot delete the current ecosystem '{name}'. Switch first.")
        sys.exit(1)

    if not eco_dir(name).exists():
        error(f"Ecosystem '{name}' does not exist")
        sys.exit(1)

    if not args.force:
        if not confirm(f"Delete ecosystem '{name}'?"):
            info("Cancelled")
            return

    delete_ecosystem(name)


def cmd_discover(args: argparse.Namespace) -> None:
    heading("Discovering paths that might need isolation")
    results = discover_paths()

    if not results:
        info("No additional paths found")
        return

    for name, size in results:
        print(f"  {name}  ({size})")

    print()
    info(f"Found {len(results)} path(s). Use 'cc-eco adopt <path>' to add them.")


def cmd_adopt(args: argparse.Namespace) -> None:
    adopt_path(args.path)


def cmd_isolate(args: argparse.Namespace) -> None:
    items = get_isolation_items()
    if not items:
        info("No paths are currently isolated")
        return

    heading("Isolated paths")
    for item in items:
        src = CLAUDE_DIR / item
        if src.is_symlink():
            target = src.resolve()
            print(f"  {item} → {target}")
        else:
            print(f"  {item} (not a symlink)")


# ─── Main ────────────────────────────────────────────────────────────────

COMMANDS = {
    "init": cmd_init,
    "snapshot": cmd_snapshot,
    "switch": cmd_switch,
    "status": cmd_status,
    "list": cmd_list,
    "delete": cmd_delete,
    "discover": cmd_discover,
    "adopt": cmd_adopt,
    "isolate": cmd_isolate,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    handler = COMMANDS.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)
