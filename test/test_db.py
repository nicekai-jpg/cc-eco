"""Tests for cc_eco.db module."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cc_eco.db import (
    save_db_state,
    restore_db_state,
    regenerate_settings,
    get_skill_names_from_state,
    get_enabled_skill_names,
    get_disabled_skill_names,
)


def _create_test_db(db_path: Path) -> None:
    """Create a minimal CC Switch database for testing."""
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.execute("CREATE TABLE skills (name TEXT, enabled_claude INTEGER)")
    c.execute("INSERT INTO skills VALUES ('skill-a', 1)")
    c.execute("INSERT INTO skills VALUES ('skill-b', 0)")

    c.execute("CREATE TABLE mcp_servers (name TEXT, enabled_claude INTEGER, server_config TEXT)")
    c.execute("INSERT INTO mcp_servers VALUES ('mcp-1', 1, '{\"command\": \"node\"}')")
    c.execute("INSERT INTO mcp_servers VALUES ('mcp-2', 0, '{}')")

    c.execute(
        "CREATE TABLE providers (app_type TEXT, is_current INTEGER, settings_config TEXT)"
    )
    c.execute(
        "INSERT INTO providers VALUES ('claude', 1, '{\"enabledPlugins\": [\"p1\"], \"hooks\": {}}')"
    )

    c.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    c.execute("INSERT INTO settings VALUES ('common_config_claude', '{\"theme\": \"dark\"}')")
    c.execute("INSERT INTO settings VALUES ('common_config_enabled', 'true')")

    conn.commit()
    conn.close()


class TestSaveDbState(unittest.TestCase):
    def test_save_creates_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            eco_dir = Path(tmp) / "eco"
            eco_dir.mkdir()

            _create_test_db(db_path)

            with patch("cc_eco.db.DB_PATH", db_path):
                state = save_db_state("test", eco_dir)

            self.assertTrue((eco_dir / "db-state.json").exists())
            self.assertEqual(state["version"], 2)
            self.assertEqual(state["name"], "test")

    def test_save_captures_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            eco_dir = Path(tmp) / "eco"
            eco_dir.mkdir()

            _create_test_db(db_path)

            with patch("cc_eco.db.DB_PATH", db_path):
                state = save_db_state("test", eco_dir)

            self.assertIn("skill-a", state["skills"])
            self.assertEqual(state["skills"]["skill-a"]["enabled_claude"], 1)
            self.assertIn("skill-b", state["skills"])
            self.assertEqual(state["skills"]["skill-b"]["enabled_claude"], 0)

    def test_save_captures_mcp_servers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            eco_dir = Path(tmp) / "eco"
            eco_dir.mkdir()

            _create_test_db(db_path)

            with patch("cc_eco.db.DB_PATH", db_path):
                state = save_db_state("test", eco_dir)

            self.assertIn("mcp-1", state["mcp_servers"])
            self.assertEqual(state["mcp_servers"]["mcp-1"]["enabled_claude"], 1)
            self.assertEqual(state["mcp_servers"]["mcp-2"]["enabled_claude"], 0)

    def test_save_captures_provider_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            eco_dir = Path(tmp) / "eco"
            eco_dir.mkdir()

            _create_test_db(db_path)

            with patch("cc_eco.db.DB_PATH", db_path):
                state = save_db_state("test", eco_dir)

            self.assertIn("enabledPlugins", state["provider_settings"])
            self.assertEqual(state["provider_settings"]["enabledPlugins"], ["p1"])


class TestRestoreDbState(unittest.TestCase):
    def test_restore_updates_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            eco_dir = Path(tmp) / "eco"
            eco_dir.mkdir()

            _create_test_db(db_path)

            # Save initial state
            with patch("cc_eco.db.DB_PATH", db_path):
                state = save_db_state("test", eco_dir)

            # Modify DB directly
            conn = sqlite3.connect(str(db_path))
            conn.execute("UPDATE skills SET enabled_claude = 0 WHERE name = 'skill-a'")
            conn.commit()
            conn.close()

            # Restore should bring it back
            with patch("cc_eco.db.DB_PATH", db_path):
                restore_db_state("test", eco_dir)

            conn = sqlite3.connect(str(db_path))
            val = conn.execute("SELECT enabled_claude FROM skills WHERE name = 'skill-a'").fetchone()[0]
            conn.close()
            self.assertEqual(val, 1)

    def test_restore_missing_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cc-switch.db"
            eco_dir = Path(tmp) / "eco"
            eco_dir.mkdir()

            _create_test_db(db_path)

            with patch("cc_eco.db.DB_PATH", db_path):
                result = restore_db_state("test", eco_dir)

            self.assertIsNone(result)


class TestSkillQueries(unittest.TestCase):
    def test_get_enabled_skill_names(self):
        state = {
            "skills": {
                "a": {"enabled_claude": 1},
                "b": {"enabled_claude": 0},
                "c": {"enabled_claude": 1},
            }
        }
        self.assertEqual(get_enabled_skill_names(state), ["a", "c"])

    def test_get_disabled_skill_names(self):
        state = {
            "skills": {
                "a": {"enabled_claude": 1},
                "b": {"enabled_claude": 0},
            }
        }
        self.assertEqual(get_disabled_skill_names(state), ["b"])

    def test_get_skill_names_from_state(self):
        state = {"skills": {"a": {}, "b": {}, "c": {}}}
        self.assertEqual(sorted(get_skill_names_from_state(state)), ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
