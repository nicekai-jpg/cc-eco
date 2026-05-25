"""Filesystem operations: symlinks, isolation, discovery."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from cc_eco.utils import (
    CLAUDE_DIR,
    ECO_DIR,
    SKILLS_DIR,
    get_current,
    get_isolation_items,
    add_isolation_item,
    info,
    warn,
    error,
    eco_dir,
    eco_json_file,
    db_state_file,
)


# ─── Init ────────────────────────────────────────────────────────────────

def init_isolation(eco_name: str) -> None:
    """Move isolated paths into snapshot directory and create symlinks back."""
    items = get_isolation_items()
    eco_path = eco_dir(eco_name)
    eco_path.mkdir(parents=True, exist_ok=True)

    for item in items:
        src = CLAUDE_DIR / item
        dst = eco_path / item

        if src.is_symlink():
            # Existing symlink: resolve and copy target, remove symlink
            real_target = src.resolve()
            if real_target.is_dir():
                shutil.copytree(str(real_target), str(dst), symlinks=True)
            else:
                shutil.copy2(str(real_target), str(dst))
            src.unlink()
        elif src.is_dir():
            shutil.move(str(src), str(dst))
        elif src.exists():
            shutil.move(str(src), str(dst))
        else:
            dst.mkdir(parents=True, exist_ok=True)

        # Create symlink: src -> dst
        src.symlink_to(str(dst))
        info(f"Isolated: {item}")

    # Create eco.json
    create_eco_json(eco_name)


def create_eco_json(eco_name: str) -> None:
    """Write initial eco.json for a new ecosystem."""
    data = {
        "name": eco_name,
        "skill_repos": [],
        "enabled_plugins": [],
        "description": "",
    }
    path = eco_json_file(eco_name)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ─── Snapshot ────────────────────────────────────────────────────────────

def copy_snapshot(src_name: str, dst_name: str) -> None:
    """Copy an ecosystem directory to create a new snapshot."""
    src_path = eco_dir(src_name)
    dst_path = eco_dir(dst_name)
    shutil.copytree(str(src_path), str(dst_path), symlinks=True)

    # Update eco.json: set name, clear skill_repos and description
    eco_path = eco_json_file(dst_name)
    if eco_path.exists():
        data = json.loads(eco_path.read_text())
        data["name"] = dst_name
        data["skill_repos"] = []
        data["description"] = ""
        eco_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # Create empty dirs in dst for any items not yet present
    for item in get_isolation_items():
        item_path = dst_path / item
        if not item_path.exists():
            item_path.mkdir(parents=True, exist_ok=True)


# ─── Switch ──────────────────────────────────────────────────────────────

def switch_symlinks(eco_name: str) -> None:
    """Replace file-level symlinks to point to the target ecosystem."""
    items = get_isolation_items()
    target_dir = eco_dir(eco_name)

    for item in items:
        src = CLAUDE_DIR / item
        if src.is_symlink():
            src.unlink()
            src.symlink_to(str(target_dir / item))
            info(f"Switched symlink: {item}")
        elif src.exists():
            warn(f"{src} is not a symlink, skipping")
        else:
            # Create new symlink
            src.symlink_to(str(target_dir / item))
            info(f"Created symlink: {item}")


# ─── Skills symlink sync ────────────────────────────────────────────────

def sync_skills_symlinks(eco_name: str) -> None:
    """Create/remove skill symlinks based on the ecosystem's db-state.json."""
    state_path = db_state_file(eco_name)
    if not state_path.exists():
        return

    state = json.loads(state_path.read_text())

    enabled = [
        name
        for name, data in state.get("skills", {}).items()
        if data.get("enabled_claude") == 1
    ]
    disabled = [
        name
        for name, data in state.get("skills", {}).items()
        if data.get("enabled_claude") == 0
    ]
    known = set(state.get("skills", {}).keys())

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # Delete disabled skills
    for skill_name in disabled:
        skill_path = SKILLS_DIR / skill_name
        if skill_path.is_symlink() or skill_path.is_dir():
            if skill_path.is_symlink() or skill_path.is_dir():
                if skill_path.is_dir() and not skill_path.is_symlink():
                    shutil.rmtree(str(skill_path))
                else:
                    skill_path.unlink()
            info(f"Removed skill: {skill_name}")

    # Create enabled skills (symlink to cc-switch)
    cc_switch_skills = Path.home() / ".cc-switch" / "skills"
    for skill_name in enabled:
        skill_path = SKILLS_DIR / skill_name
        if not skill_path.exists():
            src_skill = cc_switch_skills / skill_name
            if src_skill.is_dir():
                skill_path.symlink_to(str(src_skill))
                info(f"Linked skill: {skill_name}")

    # Clean orphan symlinks (pointing to cc-switch but not in db-state)
    if SKILLS_DIR.exists():
        for entry in SKILLS_DIR.iterdir():
            if entry.is_symlink():
                target = os.readlink(str(entry))
                cc_switch_prefix = str(Path.home() / ".cc-switch" / "skills")
                if target.startswith(cc_switch_prefix) and entry.name not in known:
                    entry.unlink()
                    info(f"Removed orphan: {entry.name}")


# ─── Adopt ───────────────────────────────────────────────────────────────

def adopt_path(path: str) -> None:
    """Move a path from ~/.claude/ into the current ecosystem snapshot."""
    src = CLAUDE_DIR / path
    if not src.exists():
        error(f"{src} does not exist")
        return

    if src.is_symlink():
        error(f"{src} is already a symlink")
        return

    current = get_current()
    if not current:
        error("Not initialized")
        return

    dst = eco_dir(current) / path
    shutil.move(str(src), str(dst))
    src.symlink_to(str(dst))

    add_isolation_item(path)

    # Create empty dirs in other snapshots
    for entry in ECO_DIR.iterdir():
        if entry.is_dir() and entry.name != current and not (entry / path).exists():
            (entry / path).mkdir(parents=True, exist_ok=True)

    info(f"Adopted: {path}")


# ─── Discover ────────────────────────────────────────────────────────────

EXCLUDE_NAMES = {
    "transcripts",
    "history.jsonl",
    "cache",
    "backups",
    "file-history",
    "session-env",
    "sessions",
    "tasks",
    "telemetry",
    "plans",
    "shell-snapshots",
    "proxy",
    "statsig",
    ".DS_Store",
}

SETTINGS_NAMES = {"settings.json", "settings.local.json"}


def discover_paths() -> list[tuple[str, str]]:
    """Find paths in ~/.claude/ that might need isolation.

    Returns list of (name, size_string) tuples.
    """
    isolated = set(get_isolation_items())
    results = []

    if not CLAUDE_DIR.exists():
        return results

    for entry in CLAUDE_DIR.iterdir():
        name = entry.name

        # Skip already isolated
        if name in isolated:
            continue

        # Skip runtime data
        if name in EXCLUDE_NAMES:
            continue

        # Skip symlinks (already managed)
        if entry.is_symlink():
            continue

        # Skip settings files (managed via DB)
        if name in SETTINGS_NAMES:
            continue

        # Get size
        try:
            if entry.is_dir():
                size = _dir_size(entry)
            else:
                size = _file_size(entry)
        except OSError:
            size = "?"

        results.append((name, size))

    return results


def _dir_size(path: Path) -> str:
    """Return human-readable directory size."""
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return _format_size(total)


def _file_size(path: Path) -> str:
    """Return human-readable file size."""
    return _format_size(path.stat().st_size)


def _format_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f}K"
    elif n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f}M"
    else:
        return f"{n / (1024 * 1024 * 1024):.1f}G"


# ─── Delete ──────────────────────────────────────────────────────────────

def delete_ecosystem(name: str) -> None:
    """Remove an ecosystem directory."""
    eco_path = eco_dir(name)
    if eco_path.exists():
        shutil.rmtree(str(eco_path))
        info(f"Ecosystem '{name}' deleted")