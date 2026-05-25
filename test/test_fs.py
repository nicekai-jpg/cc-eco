"""Tests for cc_eco.fs module."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cc_eco.fs import (
    create_eco_json,
    copy_snapshot,
    switch_symlinks,
    sync_skills_symlinks,
    discover_paths,
    adopt_path,
    delete_ecosystem,
)


class TestCreateEcoJson(unittest.TestCase):
    def test_creates_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            eco_path = Path(tmp) / "test-eco"
            eco_path.mkdir()

            with patch("cc_eco.fs.eco_json_file", lambda n: eco_path / "eco.json"):
                from cc_eco.fs import create_eco_json
                create_eco_json("test-eco")

            data = json.loads((eco_path / "eco.json").read_text())
            self.assertEqual(data["name"], "test-eco")
            self.assertEqual(data["skill_repos"], [])
            self.assertEqual(data["description"], "")


class TestSwitchSymlinks(unittest.TestCase):
    def test_switches_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = Path(tmp) / "claude"
            claude_dir.mkdir()
            eco_a = Path(tmp) / "eco-a"
            eco_b = Path(tmp) / "eco-b"
            eco_a.mkdir()
            eco_b.mkdir()

            # Create a directory in eco-a and symlink to it
            (eco_a / "skills").mkdir()
            (claude_dir / "skills").symlink_to(str(eco_a / "skills"))

            # Create corresponding dir in eco-b
            (eco_b / "skills").mkdir()

            with patch("cc_eco.fs.CLAUDE_DIR", claude_dir), \
                 patch("cc_eco.fs.get_isolation_items", return_value=["skills"]), \
                 patch("cc_eco.fs.eco_dir", lambda n: eco_b if n == "eco-b" else eco_a):
                switch_symlinks("eco-b")

            target = os.readlink(str(claude_dir / "skills"))
            self.assertIn("eco-b", target)


class TestDiscoverPaths(unittest.TestCase):
    def test_finds_un_isolated_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = Path(tmp) / "claude"
            claude_dir.mkdir()
            (claude_dir / "skills").mkdir()
            (claude_dir / "commands").mkdir()
            (claude_dir / "settings.json").write_text("{}")

            with patch("cc_eco.fs.CLAUDE_DIR", claude_dir), \
                 patch("cc_eco.fs.get_isolation_items", return_value=[]):
                results = discover_paths()

            names = [r[0] for r in results]
            self.assertIn("skills", names)
            self.assertIn("commands", names)
            self.assertNotIn("settings.json", names)

    def test_excludes_runtime_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            claude_dir = Path(tmp) / "claude"
            claude_dir.mkdir()
            (claude_dir / "transcripts").mkdir()
            (claude_dir / "cache").mkdir()
            (claude_dir / "my-data").mkdir()

            with patch("cc_eco.fs.CLAUDE_DIR", claude_dir), \
                 patch("cc_eco.fs.get_isolation_items", return_value=[]):
                results = discover_paths()

            names = [r[0] for r in results]
            self.assertNotIn("transcripts", names)
            self.assertNotIn("cache", names)
            self.assertIn("my-data", names)


class TestDeleteEcosystem(unittest.TestCase):
    def test_deletes_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            eco_path = Path(tmp) / "test-eco"
            eco_path.mkdir()
            (eco_path / "some-file").write_text("data")

            with patch("cc_eco.fs.eco_dir", lambda n: eco_path):
                delete_ecosystem("test-eco")

            self.assertFalse(eco_path.exists())


if __name__ == "__main__":
    unittest.main()
