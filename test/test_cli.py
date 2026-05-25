"""Tests for cc_eco.cli module."""

import unittest
from argparse import Namespace

from cc_eco.cli import build_parser


class TestParser(unittest.TestCase):
    def setUp(self):
        self.parser = build_parser()

    def test_init_command(self):
        args = self.parser.parse_args(["init", "my-eco"])
        self.assertEqual(args.command, "init")
        self.assertEqual(args.name, "my-eco")

    def test_snapshot_command(self):
        args = self.parser.parse_args(["snapshot", "new-eco"])
        self.assertEqual(args.command, "snapshot")
        self.assertEqual(args.name, "new-eco")

    def test_switch_command(self):
        args = self.parser.parse_args(["switch", "target"])
        self.assertEqual(args.command, "switch")
        self.assertEqual(args.name, "target")
        self.assertFalse(args.no_restart)

    def test_switch_no_restart(self):
        args = self.parser.parse_args(["switch", "target", "--no-restart"])
        self.assertTrue(args.no_restart)

    def test_delete_command(self):
        args = self.parser.parse_args(["delete", "old-eco"])
        self.assertEqual(args.command, "delete")
        self.assertEqual(args.name, "old-eco")
        self.assertFalse(args.force)

    def test_delete_force(self):
        args = self.parser.parse_args(["delete", "old-eco", "--force"])
        self.assertTrue(args.force)

    def test_adopt_command(self):
        args = self.parser.parse_args(["adopt", "skills"])
        self.assertEqual(args.command, "adopt")
        self.assertEqual(args.path, "skills")

    def test_status_command(self):
        args = self.parser.parse_args(["status"])
        self.assertEqual(args.command, "status")

    def test_list_command(self):
        args = self.parser.parse_args(["list"])
        self.assertEqual(args.command, "list")

    def test_discover_command(self):
        args = self.parser.parse_args(["discover"])
        self.assertEqual(args.command, "discover")

    def test_isolate_command(self):
        args = self.parser.parse_args(["isolate"])
        self.assertEqual(args.command, "isolate")


if __name__ == "__main__":
    unittest.main()
