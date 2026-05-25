"""Cross-platform process restart for CC Switch and Claude Code."""

import platform
import subprocess
import sys
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
    """Restart CC Switch and Claude Code after ecosystem switch.

    If no_restart is True, skip all restart logic.
    """
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
    """Restart processes on macOS using pkill, open, and osascript."""
    # Kill CC Switch
    _pkill("cc-switch")
    # Kill Claude Code
    _pkill("claude")

    import time
    time.sleep(1)

    # Restart CC Switch
    try:
        subprocess.run(["open", "/Applications/CC Switch.app"], check=False)
        info("CC Switch restarted")
    except FileNotFoundError:
        warn("Cannot start CC Switch: 'open' command not found")

    # Restart Claude Code in a new terminal
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
    """Restart processes on Linux."""
    # Kill CC Switch
    _pkill("cc-switch")
    # Kill Claude Code
    _pkill("claude")

    import time
    time.sleep(1)

    # Restart CC Switch
    _start_cc_switch_linux()

    # Restart Claude Code in a new terminal
    _start_claude_linux()


def _start_cc_switch_linux() -> None:
    """Try to start CC Switch on Linux."""
    # Try running from PATH
    if which("cc-switch"):
        subprocess.Popen(["cc-switch"], start_new_session=True)
        info("CC Switch restarted")
        return

    # Try systemd user service
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
    """Try to start Claude Code in a new terminal on Linux."""
    # Try common terminal emulators
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

    # Fallback: try xdg-terminal-emulator
    if which("xdg-terminal-emulator"):
        subprocess.Popen(["xdg-terminal-emulator", "claude"], start_new_session=True)
        info("Claude Code restarted")
        return

    warn("Cannot start Claude Code in a terminal. Please start it manually.")


# ─── Windows ─────────────────────────────────────────────────────────────

def _restart_windows() -> None:
    """Restart processes on Windows (best-effort)."""
    # Kill
    for proc in ("cc-switch.exe", "claude.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", proc], check=False, capture_output=True)
        except FileNotFoundError:
            pass

    import time
    time.sleep(1)

    # Restart CC Switch
    try:
        os_path = "C:\\Program Files\\CC Switch\\cc-switch.exe"
        subprocess.Popen([os_path], start_new_session=True)
        info("CC Switch restarted")
    except FileNotFoundError:
        warn("Cannot start CC Switch on Windows")

    # Restart Claude Code
    try:
        subprocess.Popen(["claude"], start_new_session=True)
        info("Claude Code restarted")
    except FileNotFoundError:
        warn("Cannot start Claude Code on Windows")


# ─── Helpers ─────────────────────────────────────────────────────────────

def _pkill(name: str) -> None:
    """Kill a process by name. Works on macOS and Linux."""
    try:
        subprocess.run(["pkill", "-x", name], check=False, capture_output=True)
    except FileNotFoundError:
        # pkill not available (unlikely on macOS/Linux)
        warn(f"Cannot kill {name}: 'pkill' not found")