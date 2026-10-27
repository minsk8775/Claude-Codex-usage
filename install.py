"""Create the Claude Codex Usage desktop and startup shortcuts."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_SCRIPT = BASE_DIR / "claude_usage.pyw"
ICON = BASE_DIR / "assets" / "claude-usage.ico"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ClaudeCodexUsage"
AUTO_FILE = STATE_DIR / "auto.enabled"
PYTHONW_FILE = STATE_DIR / "pythonw.path"
STARTUP = Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup"

# This app's own control ports (keep in sync with claude_usage.pyw). The
# installer stops the currently-running widget and watcher through these before
# starting fresh copies, so re-running install.cmd always refreshes them to the
# latest code (the watcher binds its port exclusively, so a stale one would
# otherwise keep running and block the new one).
APP_MAIN_PORT = 47671
APP_WATCH_PORT = 47672

# Windows' own shortcut object, driven from PowerShell. Values travel in
# environment variables so paths with quotes or non-ASCII characters (an
# apostrophe in the user name, a OneDrive '문서' folder) need no escaping.
SHORTCUT_SCRIPT = (
    "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:CCU_LINK);"
    "$s.TargetPath = $env:CCU_TARGET;"
    "$s.Arguments = $env:CCU_ARGS;"
    "$s.WorkingDirectory = $env:CCU_DIR;"
    "$s.Description = $env:CCU_DESC;"
    "$s.IconLocation = $env:CCU_ICON + ',0';"
    "$s.Save()"
)


def _send_exit(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b"exit", ("127.0.0.1", port))
    except OSError:
        pass


def desktop_path():
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
    ) as key:
        return Path(os.path.expandvars(winreg.QueryValueEx(key, "Desktop")[0]))


def managed_pythonw():
    pythonw = Path(sys.base_prefix) / "pythonw.exe"
    if not pythonw.exists():
        raise RuntimeError("pythonw.exe was not found: %s" % pythonw)
    return pythonw


def create_shortcut(path, pythonw, arguments, description):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Start in the data folder, not the program folder, so a running widget or
    # watcher never stops the program folder from being deleted or replaced.
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        CCU_LINK=str(path),
        CCU_TARGET=str(pythonw),
        CCU_ARGS=arguments,
        CCU_DIR=str(STATE_DIR),
        CCU_DESC=description,
        CCU_ICON=str(ICON),
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_SCRIPT],
        env=env,
        check=True,
        timeout=60,
    )


def start(pythonw, *arguments):
    subprocess.Popen(
        [str(pythonw), str(APP_SCRIPT), *arguments],
        cwd=str(STATE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000,
        close_fds=True,
    )


def main():
    pythonw = managed_pythonw()
    # Stop this app's own running widget and watcher so the fresh copies below
    # run the latest code (the watcher holds its port exclusively).
    _send_exit(APP_MAIN_PORT)
    _send_exit(APP_WATCH_PORT)
    time.sleep(0.6)
    desktop_link = desktop_path() / "Claude Codex Usage.lnk"
    startup_link = STARTUP / "Claude Codex Usage Watcher.lnk"

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    AUTO_FILE.write_text("enabled", encoding="utf-8")
    PYTHONW_FILE.write_text(str(pythonw), encoding="utf-8")
    create_shortcut(
        desktop_link,
        pythonw,
        '"%s"' % APP_SCRIPT,
        "Open or show the Claude Codex Usage window",
    )
    create_shortcut(
        startup_link,
        pythonw,
        '"%s" --watch' % APP_SCRIPT,
        "Start Claude Codex Usage when Claude Code opens",
    )

    start(pythonw, "--watch")
    start(pythonw)
    print("Claude Codex Usage installation complete.")
    print("Desktop shortcut:", desktop_link)
    print("Startup shortcut:", startup_link)


if __name__ == "__main__":
    main()
