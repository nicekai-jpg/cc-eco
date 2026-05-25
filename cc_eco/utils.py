"""Constants, colors, and utility functions."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Paths ---
HOME = Path.home()
ECO_DIR = HOME / ".claude-ecosystems"
CURRENT_FILE = ECO_DIR / ".current"
ISOLATION_FILE = ECO_DIR / ".isolation"
DB_PATH = HOME / ".cc-switch" / "cc-switch.db"
CLAUDE_DIR = HOME / ".claude"
SETTINGS_FILE = CLAUDE_DIR / "settings.json"
SKILLS_DIR = CLAUDE_DIR / "skills"

# --- Colors ---
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{GREEN}✓{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}⚠{NC} {msg}")


def error(msg: str) -> None:
    print(f"{RED}✗{NC} {msg}", file=sys.stderr)


def step(msg: str) -> None:
    print(f"{BLUE}→{NC} {msg}")


def heading(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{msg}{NC}")


def require_init() -> None:
    """Exit if cc-eco has not been initialized."""
    if not CURRENT_FILE.exists():
        error("cc-eco is not initialized. Run: cc-eco init <name>")
        sys.exit(1)


def get_current() -> str | None:
    """Return the name of the current ecosystem, or None."""
    if CURRENT_FILE.exists():
        return CURRENT_FILE.read_text().strip() or None
    return None


def set_current(name: str) -> None:
    CURRENT_FILE.write_text(name)


def get_isolation_items() -> list[str]:
    """Return list of paths that should be isolated per ecosystem."""
    if ISOLATION_FILE.exists():
        lines = ISOLATION_FILE.read_text().strip().splitlines()
        return [l.strip() for l in lines if l.strip()]
    return []


def add_isolation_item(path: str) -> None:
    """Append a path to the isolation file."""
    items = get_isolation_items()
    if path not in items:
        items.append(path)
        ISOLATION_FILE.write_text("\n".join(items) + "\n")


def confirm(prompt: str) -> bool:
    """Ask user for yes/no confirmation."""
    try:
        answer = input(f"{YELLOW}{prompt} [y/N]{NC} ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def backup_db() -> Path | None:
    """Create a timestamped backup of the CC Switch database."""
    if not DB_PATH.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = DB_PATH.parent / f"cc-switch.db.backup.{ts}"
    shutil.copy2(DB_PATH, backup)
    return backup


def eco_dir(name: str) -> Path:
    """Return the directory for a given ecosystem name."""
    return ECO_DIR / name


def db_state_file(name: str) -> Path:
    return eco_dir(name) / "db-state.json"


def eco_json_file(name: str) -> Path:
    return eco_dir(name) / "eco.json"


def load_db_state(name: str) -> dict | None:
    path = db_state_file(name)
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_eco_json(name: str) -> dict | None:
    path = eco_json_file(name)
    if path.exists():
        return json.loads(path.read_text())
    return None
