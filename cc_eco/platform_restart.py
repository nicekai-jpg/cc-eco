"""Cross-platform process restart for CC Switch and Claude Code."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
from shutil import which

from cc_eco.utils import info, warn


def get_platform() -> str:
    """Detect the current platform: 'macos', 'linux', or 'windows'."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    elif system == "Windows":
        return "windows"
    return "unknown"


def restart_processes(no_restart: bool = False) -> None:
    """Restart CC Switch and Claude Code after ecosystem switch."""
    if no_restart:
        info("Switched (no restart). Please restart Claude Code and CC Switch manually.")
        return

    plat = get_platform()
    if plat == "macos":
        _restart_macos()
    elif plat == "linux":
        _restart_linux()
    elif plat == "windows":
        _restart_windows()
    else:
        warn(f"Unknown platform '{plat}', please restart manually")


# ─── macOS ───────────────────────────────────────────────────────────────

def _restart_macos() -> None:
    _pkill("cc-switch")
    _pkill("claude")
    time.sleep(1)

    try:
        subprocess.run(["open", "/Applications/CC Switch.app"], check=False)
        info("CC Switch restarted")
    except FileNotFoundError:
        warn("Cannot start CC Switch: 'open' command not found")

    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "Terminal" to do script "claude"'],
            check=False,
        )
        info("Claude Code restarted")
    except FileNotFoundError:
        warn("Cannot start Claude Code: 'osascript' not found")


# ─── Linux ───────────────────────────────────────────────────────────────

def _restart_linux() -> None:
    _pkill("cc-switch")
    _pkill("claude")
    time.sleep(1)
    _start_cc_switch_linux()
    _start_claude_linux()


def _start_cc_switch_linux() -> None:
    if which("cc-switch"):
        subprocess.Popen(["cc-switch"], start_new_session=True)
        info("CC Switch restarted")
        return

    try:
        result = subprocess.run(
            ["systemctl", "--user", "start", "cc-switch"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            info("CC Switch restarted (systemd)")
            return
    except FileNotFoundError:
        pass

    warn("Cannot start CC Switch. Please start it manually.")


def _start_claude_linux() -> None:
    terminals = [
        ("gnome-terminal", ["gnome-terminal", "--", "claude"]),
        ("konsole", ["konsole", "-e", "claude"]),
        ("alacritty", ["alacritty", "-e", "claude"]),
        ("kitty", ["kitty", "claude"]),
        ("xfce4-terminal", ["xfce4-terminal", "-x", "claude"]),
    ]

    for name, cmd in terminals:
        if which(name):
            subprocess.Popen(cmd, start_new_session=True)
            info(f"Claude Code restarted in {name}")
            return

    if which("xdg-terminal-emulator"):
        subprocess.Popen(["xdg-terminal-emulator", "claude"], start_new_session=True)
        info("Claude Code restarted")
        return

    warn("Cannot start Claude Code in a terminal. Please start it manually.")


# ─── Windows ─────────────────────────────────────────────────────────────

def _restart_windows() -> None:
    for proc in ("cc-switch.exe", "claude.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", proc], check=False, capture_output=True)
        except FileNotFoundError:
            pass

    time.sleep(1)

    # Try to start CC Switch
    cc_switch_path = os.environ.get(
        "CC_SWITCH_PATH",
        r"C:\Program Files\CC Switch\cc-switch.exe",
    )
    if os.path.isfile(cc_switch_path):
        subprocess.Popen([cc_switch_path], start_new_session=True)
        info("CC Switch restarted")
    else:
        warn("Cannot start CC Switch on Windows")

    # Try to start Claude Code
    if which("claude"):
        subprocess.Popen(["claude"], start_new_session=True)
        info("Claude Code restarted")
    else:
        warn("Cannot start Claude Code on Windows")


# ─── Helpers ─────────────────────────────────────────────────────────────

def _pkill(name: str) -> None:
    """Kill a process by name. Works on macOS and Linux."""
    try:
        subprocess.run(["pkill", "-x", name], check=False, capture_output=True)
    except FileNotFoundError:
        warn(f"Cannot kill {name}: 'pkill' not found")