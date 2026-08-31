"""Create the Claude Codex Usage desktop and startup shortcuts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_SCRIPT = BASE_DIR / "claude_usage.pyw"
ICON = BASE_DIR / "assets" / "claude-usage.ico"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ClaudeCodexUsage"
AUTO_FILE = STATE_DIR / "auto.enabled"
PYTHONW_FILE = STATE_DIR / "pythonw.path"
STARTUP = Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Startup"


def ensure_pywin32():
    """Make sure pywin32 is importable.

    Under ``uv run --with pywin32`` the package is already present. When the
    installer runs on a plain Python interpreter (no uv), install it with pip
    into that interpreter so the shortcut creation below can use it.
    """

    try:
        import pythoncom  # noqa: F401
        import win32com  # noqa: F401

        return
    except ImportError:
        pass

    print("pywin32가 없어 설치합니다...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--user", "pywin32"]
    )

    try:
        import pythoncom  # noqa: F401
        import win32com  # noqa: F401
    except ImportError as error:  # pragma: no cover - defensive
        raise RuntimeError(
            "pywin32 설치 후에도 불러오지 못했습니다. "
            "'python -m pip install pywin32'를 직접 실행해 보세요."
        ) from error


def stop_legacy_processes():
    from win32com.client import GetObject

    base_dir = str(BASE_DIR).lower()
    legacy_names = (
        "claudepet.ps1",
        "watch-claude.ps1",
        "start-pet.vbs",
        "toggle-usage.ps1",
        "toggle-usage.vbs",
        "watch-claude.vbs",
    )
    services = GetObject("winmgmts:")
    for process in services.ExecQuery(
        "SELECT Name, CommandLine FROM Win32_Process "
        "WHERE Name = 'powershell.exe' OR Name = 'wscript.exe'"
    ):
        command = (process.CommandLine or "").lower()
        if base_dir in command and any(name in command for name in legacy_names):
            process.Terminate()


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
        raise RuntimeError("pythonw.exe를 찾지 못했습니다: %s" % pythonw)
    return pythonw


def create_shortcut(path, pythonw, arguments, description):
    import pythoncom
    from win32com.shell import shell

    path.parent.mkdir(parents=True, exist_ok=True)
    link = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink,
        None,
        pythoncom.CLSCTX_INPROC_SERVER,
        shell.IID_IShellLink,
    )
    link.SetPath(str(pythonw))
    link.SetArguments(arguments)
    link.SetWorkingDirectory(str(BASE_DIR))
    link.SetDescription(description)
    link.SetIconLocation(str(ICON), 0)
    link.SetShowCmd(0)
    persist = link.QueryInterface(pythoncom.IID_IPersistFile)
    persist.Save(str(path), 0)


def start(pythonw, *arguments):
    subprocess.Popen(
        [str(pythonw), str(APP_SCRIPT), *arguments],
        cwd=str(BASE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x08000000,
        close_fds=True,
    )


def main():
    ensure_pywin32()
    pythonw = managed_pythonw()
    stop_legacy_processes()
    desktop = desktop_path()
    desktop_link = desktop / "Claude Codex Usage.lnk"
    legacy_link = desktop / "Claude Codex Usage Toggle.lnk"
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
    try:
        legacy_link.unlink()
    except FileNotFoundError:
        pass

    start(pythonw, "--watch")
    start(pythonw)
    print("Claude Codex Usage installation complete.")
    print("Desktop shortcut:", desktop_link)
    print("Startup shortcut:", startup_link)


if __name__ == "__main__":
    main()
