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

# Shortcuts are written through Windows' own shell-link object (IShellLinkW),
# called with ctypes. Unlike WScript.Shell it keeps every path in Unicode, so a
# user or folder name outside the system code page still works.
CLSID_SHELL_LINK = "{00021401-0000-0000-C000-000000000046}"
IID_SHELL_LINK_W = "{000214F9-0000-0000-C000-000000000046}"
IID_PERSIST_FILE = "{0000010B-0000-0000-C000-000000000046}"


def _guid(text):
    import ctypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    guid = GUID()
    ctypes.oledll.ole32.CLSIDFromString(text, ctypes.byref(guid))
    return guid


def com_method(obj, index, *argtypes):
    """Method ``index`` of a COM object's vtable; a failing HRESULT raises OSError."""
    import ctypes

    vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, *argtypes)(vtable[index])


def shell_link():
    """A new IShellLinkW and its IPersistFile; release both with com_release."""
    import ctypes

    try:
        ctypes.oledll.ole32.CoInitialize(None)
    except OSError:
        pass  # already initialised in another mode; COM still works
    link, persist = ctypes.c_void_p(), ctypes.c_void_p()
    ctypes.oledll.ole32.CoCreateInstance(
        ctypes.byref(_guid(CLSID_SHELL_LINK)), None, 1,  # CLSCTX_INPROC_SERVER
        ctypes.byref(_guid(IID_SHELL_LINK_W)), ctypes.byref(link))
    com_method(link, 0, ctypes.c_void_p, ctypes.c_void_p)(  # QueryInterface
        link, ctypes.byref(_guid(IID_PERSIST_FILE)), ctypes.byref(persist))
    return link, persist


def com_release(*objects):
    import ctypes

    for obj in objects:
        vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])(obj)


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
    from ctypes import c_int, c_wchar_p

    path.parent.mkdir(parents=True, exist_ok=True)
    # Start in the data folder, not the program folder, so a running widget or
    # watcher never stops the program folder from being deleted or replaced.
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    link, persist = shell_link()
    try:
        com_method(link, 20, c_wchar_p)(link, str(pythonw))            # SetPath
        com_method(link, 11, c_wchar_p)(link, arguments)               # SetArguments
        com_method(link, 9, c_wchar_p)(link, str(STATE_DIR))           # SetWorkingDirectory
        com_method(link, 7, c_wchar_p)(link, description)              # SetDescription
        com_method(link, 17, c_wchar_p, c_int)(link, str(ICON), 0)     # SetIconLocation
        com_method(persist, 6, c_wchar_p, c_int)(persist, str(path), 1)  # Save
    finally:
        com_release(persist, link)


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
