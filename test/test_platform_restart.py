"""Tests for cc_eco.platform_restart module."""

import unittest
from unittest.mock import patch, MagicMock

from cc_eco.platform_restart import get_platform, restart_processes


class TestGetPlatform(unittest.TestCase):
    def test_macos(self):
        with patch("cc_eco.platform_restart.platform.system", return_value="Darwin"):
            self.assertEqual(get_platform(), "macos")

    def test_linux(self):
        with patch("cc_eco.platform_restart.platform.system", return_value="Linux"):
            self.assertEqual(get_platform(), "linux")

    def test_windows(self):
        with patch("cc_eco.platform_restart.platform.system", return_value="Windows"):
            self.assertEqual(get_platform(), "windows")

    def test_unknown(self):
        with patch("cc_eco.platform_restart.platform.system", return_value="FreeBSD"):
            self.assertEqual(get_platform(), "unknown")


class TestRestartProcesses(unittest.TestCase):
    def test_no_restart_flag(self):
        with patch("cc_eco.platform_restart.info") as mock_info:
            restart_processes(no_restart=True)
            mock_info.assert_called_once()
            self.assertIn("no restart", mock_info.call_args[0][0])

    def test_dispatches_to_macos(self):
        with patch("cc_eco.platform_restart.get_platform", return_value="macos"), \
             patch("cc_eco.platform_restart._restart_macos") as mock_mac:
            restart_processes(no_restart=False)
            mock_mac.assert_called_once()

    def test_dispatches_to_linux(self):
        with patch("cc_eco.platform_restart.get_platform", return_value="linux"), \
             patch("cc_eco.platform_restart._restart_linux") as mock_linux:
            restart_processes(no_restart=False)
            mock_linux.assert_called_once()

    def test_dispatches_to_windows(self):
        with patch("cc_eco.platform_restart.get_platform", return_value="windows"), \
             patch("cc_eco.platform_restart._restart_windows") as mock_win:
            restart_processes(no_restart=False)
            mock_win.assert_called_once()


if __name__ == "__main__":
    unittest.main()
