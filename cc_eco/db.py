"""SQLite database operations for CC Switch.

The CC Switch database (~/.cc-switch/cc-switch.db) stores Claude Code
configuration. We save/restore only the fields that differ between
ecosystems, not the entire database.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from cc_eco.utils import DB_PATH, SETTINGS_FILE, info, warn


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# ─── Load saved state ────────────────────────────────────────────────────

def load_db_state(name: str) -> dict | None:
    """Load db-state.json for an ecosystem. Returns None if not found."""
    from cc_eco.utils import db_state_file

    path = db_state_file(name)
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_eco_json(name: str) -> dict | None:
    """Load eco.json for an ecosystem. Returns None if not found."""
    from cc_eco.utils import eco_json_file

    path = eco_json_file(name)
    if path.exists():
        return json.loads(path.read_text())
    return None


# ─── Save / Restore ─────────────────────────────────────────────────────

def save_db_state(eco_name: str, eco_dir: Path) -> dict:
    """Save current DB state to db-state.json in the ecosystem directory.

    Only saves the fields that differ between ecosystems:
    - skills.enabled_claude
    - mcp_servers.enabled_claude
    - providers.settings_config (enabledPlugins, hooks)
    - settings.common_config_claude
    """
    state = {
        "version": 2,
        "name": eco_name,
        "skills": {},
        "mcp_servers": {},
        "provider_settings": {},
        "common_config": None,
    }

    if not DB_PATH.exists():
        warn("CC Switch database not found, saving empty state")
        _write_state_file(eco_dir, state)
        return state

    conn = _connect()
    try:
        # Skills
        for row in conn.execute("SELECT name, enabled_claude FROM skills"):
            state["skills"][row["name"]] = {"enabled_claude": row["enabled_claude"]}

        # MCP servers
        for row in conn.execute("SELECT name, enabled_claude FROM mcp_servers"):
            state["mcp_servers"][row["name"]] = {"enabled_claude": row["enabled_claude"]}

        # Provider settings (current claude provider)
        row = conn.execute(
            "SELECT settings_config FROM providers WHERE is_current = 1 AND app_type = ?",
            ("claude",),
        ).fetchone()
        if row and row["settings_config"]:
            try:
                settings = json.loads(row["settings_config"])
                state["provider_settings"] = {
                    "enabledPlugins": settings.get("enabledPlugins", []),
                    "hooks": settings.get("hooks", {}),
                }
            except json.JSONDecodeError:
                pass

        # Common config
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("common_config_claude",),
        ).fetchone()
        if row and row["value"]:
            try:
                state["common_config"] = json.loads(row["value"])
            except json.JSONDecodeError:
                pass
    finally:
        conn.close()

    _write_state_file(eco_dir, state)
    info(f"DB state saved for '{eco_name}'")
    return state


def restore_db_state(eco_name: str, eco_dir: Path) -> dict | None:
    """Restore DB state from db-state.json.

    Only updates the specific fields that were saved, preserving all other data.
    """
    state_path = eco_dir / "db-state.json"
    if not state_path.exists():
        warn(f"No db-state.json found for '{eco_name}'")
        return None

    state = json.loads(state_path.read_text())

    if not DB_PATH.exists():
        warn("CC Switch database not found, cannot restore")
        return None

    conn = _connect()
    try:
        cursor = conn.cursor()

        # Restore skills enabled state
        for skill_name, skill_data in state.get("skills", {}).items():
            cursor.execute(
                "UPDATE skills SET enabled_claude = ? WHERE name = ?",
                (skill_data["enabled_claude"], skill_name),
            )

        # Restore MCP servers enabled state
        for server_name, server_data in state.get("mcp_servers", {}).items():
            cursor.execute(
                "UPDATE mcp_servers SET enabled_claude = ? WHERE name = ?",
                (server_data["enabled_claude"], server_name),
            )

        # Restore provider settings
        provider_settings = state.get("provider_settings", {})
        if provider_settings:
            row = cursor.execute(
                "SELECT settings_config FROM providers WHERE is_current = 1 AND app_type = ?",
                ("claude",),
            ).fetchone()
            if row and row[0]:
                try:
                    current = json.loads(row[0])
                except json.JSONDecodeError:
                    current = {}
            else:
                current = {}

            if "enabledPlugins" in provider_settings:
                current["enabledPlugins"] = provider_settings["enabledPlugins"]
            if "hooks" in provider_settings:
                current["hooks"] = provider_settings["hooks"]

            cursor.execute(
                "UPDATE providers SET settings_config = ? WHERE is_current = 1 AND app_type = ?",
                (json.dumps(current, ensure_ascii=False), "claude"),
            )

        # Restore common config
        common_config = state.get("common_config")
        if common_config is not None:
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("common_config_claude", json.dumps(common_config, ensure_ascii=False)),
            )

        conn.commit()
        info(f"DB state restored for '{eco_name}'")
    except Exception as e:
        conn.rollback()
        warn(f"DB restore failed: {e}")
        return None
    finally:
        conn.close()

    return state


# ─── Regenerate settings.json ───────────────────────────────────────────

def regenerate_settings() -> None:
    """Regenerate ~/.claude/settings.json from the current DB state.

    Reads the current provider's settings_config, merges common config
    if enabled, adds enabled MCP servers, and writes the result.
    """
    if not DB_PATH.exists():
        return

    conn = _connect()
    try:
        # Read current provider settings
        row = conn.execute(
            "SELECT settings_config FROM providers WHERE is_current = 1 AND app_type = ?",
            ("claude",),
        ).fetchone()

        if not row or not row["settings_config"]:
            return

        try:
            settings = json.loads(row["settings_config"])
        except json.JSONDecodeError:
            return

        # Merge common config if enabled
        common_row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("common_config_claude",),
        ).fetchone()
        common_enabled_row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            ("common_config_enabled",),
        ).fetchone()

        if (
            common_row
            and common_row["value"]
            and common_enabled_row
            and common_enabled_row["value"] == "true"
        ):
            try:
                common = json.loads(common_row["value"])
                settings = {**common, **settings}
            except (json.JSONDecodeError, TypeError):
                pass

        # Add enabled MCP servers
        mcp_servers = {}
        for mcp_row in conn.execute(
            "SELECT name, server_config FROM mcp_servers WHERE enabled_claude = 1"
        ):
            try:
                mcp_servers[mcp_row["name"]] = json.loads(mcp_row["server_config"])
            except (json.JSONDecodeError, TypeError):
                mcp_servers[mcp_row["name"]] = {}

        if mcp_servers:
            settings["mcpServers"] = mcp_servers

        # Sanitize: remove internal fields
        for key in ("apiFormat", "apiKey", "baseUrl", "model", "providerName"):
            settings.pop(key, None)

        # Write
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False))
        info("settings.json regenerated")
    finally:
        conn.close()


# ─── Skill queries ──────────────────────────────────────────────────────

def get_skill_names_from_state(state: dict) -> list[str]:
    return list(state.get("skills", {}).keys())


def get_enabled_skill_names(state: dict) -> list[str]:
    return [
        name
        for name, data in state.get("skills", {}).items()
        if data.get("enabled_claude") == 1
    ]


def get_disabled_skill_names(state: dict) -> list[str]:
    return [
        name
        for name, data in state.get("skills", {}).items()
        if data.get("enabled_claude") == 0
    ]


# ─── Internal ───────────────────────────────────────────────────────────

def _write_state_file(eco_dir: Path, state: dict) -> None:
    eco_dir.mkdir(parents=True, exist_ok=True)
    (eco_dir / "db-state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False)
    )
