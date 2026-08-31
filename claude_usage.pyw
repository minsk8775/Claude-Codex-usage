"""Claude Codex Usage desktop widget.

This GUI runs directly under pythonw.exe without an intermediary script host.
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox


BASE_DIR = Path(__file__).resolve().parent
USAGE_SCRIPT = BASE_DIR / "usage.py"
LATEST = BASE_DIR / "latest.json"
CODEX_SCRIPT = BASE_DIR / "codex_usage.py"
CODEX_LATEST = BASE_DIR / "codex_latest.json"
ERROR_LOG = BASE_DIR / "error.log"
ICON_PATH = BASE_DIR / "assets" / "claude-usage.ico"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "ClaudeCodexUsage"
AUTO_FILE = STATE_DIR / "auto.enabled"
SETTINGS_FILE = STATE_DIR / "settings.json"
PYTHONW_FILE = STATE_DIR / "pythonw.path"
DESKTOP = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
try:
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
    ) as key:
        DESKTOP = Path(os.path.expandvars(winreg.QueryValueEx(key, "Desktop")[0]))
except (OSError, ImportError):
    pass
STARTUP = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
DESKTOP_LINK = DESKTOP / "Claude Codex Usage.lnk"
LEGACY_DESKTOP_LINK = DESKTOP / "Claude Codex Usage Toggle.lnk"
STARTUP_LINK = STARTUP / "Claude Codex Usage Watcher.lnk"
MAIN_PORT = 47671
WATCH_PORT = 47672
CREATE_NO_WINDOW = 0x08000000
UPDATE_SOURCES = ("claude_usage.pyw", "usage.py", "codex_usage.py")

# The widget shows one page per source and flips between them with the on-screen
# arrows. Each page reads its own latest.json and refreshes with its own script.
# "connect" marks a source whose first sync may need an interactive login step
# (Claude opens a browser); Codex reads local files, so it never does.
SOURCES = (
    {
        "key": "claude",
        "title": "CLAUDE USAGE",
        "latest": LATEST,
        "script": USAGE_SCRIPT,
        "connect": True,
    },
    {
        "key": "codex",
        "title": "CODEX USAGE",
        "latest": CODEX_LATEST,
        "script": CODEX_SCRIPT,
        "connect": False,
    },
)
SOURCE_BY_KEY = {source["key"]: source for source in SOURCES}

# View modes, chosen from the notification-icon right-click menu:
#   both_stacked - both sources at once, stacked in one window (default)
#   both_paged   - both sources, one per page, flipped with the on-screen arrows
#   claude       - Claude only
#   codex        - Codex only
VIEW_MODES = ("both_stacked", "both_paged", "claude", "codex")
DEFAULT_MODE = "both_stacked"
# (menu id, mode key, label) rendered in the tray menu, in this order.
MODE_MENU = (
    (2001, "claude", "Claude만 보기"),
    (2002, "codex", "Codex만 보기"),
    (2003, "both_stacked", "둘 다 보기"),
    (2004, "both_paged", "둘 다 (좌우 전환)"),
)
MODE_BY_ID = {menu_id: mode for menu_id, mode, _label in MODE_MENU}


def log_error(value):
    try:
        with ERROR_LOG.open("a", encoding="utf-8") as stream:
            stream.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), value))
    except OSError:
        pass


def python_console():
    executable = Path(sys.executable)
    candidate = executable.with_name("python.exe")
    return str(candidate if candidate.exists() else executable)


def run_script(script, *arguments, timeout=60):
    command = [python_console(), str(script), *arguments]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return subprocess.run(
        command,
        cwd=str(BASE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startup,
        creationflags=CREATE_NO_WINDOW,
        timeout=timeout,
        check=False,
    )


def run_usage(*arguments, timeout=60):
    return run_script(USAGE_SCRIPT, *arguments, timeout=timeout)


def run_git(*arguments, timeout=90):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return subprocess.run(
        ["git", *arguments],
        cwd=str(BASE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0"),
        startupinfo=startup,
        creationflags=CREATE_NO_WINDOW,
        timeout=timeout,
        check=False,
    )


def pull_updates():
    """Fast-forward the checkout to origin.

    Returns True when the code this process is running actually changed. Local
    edits make the fast-forward fail, which leaves the checkout untouched.
    """
    if not (BASE_DIR / ".git").exists():
        return False
    try:
        before = run_git("rev-parse", "HEAD")
        if before.returncode:
            return False
        pulled = run_git("pull", "--ff-only")
        if pulled.returncode:
            log_error("update skipped: %s" % (pulled.stderr or pulled.stdout).strip())
            return False
        after = run_git("rev-parse", "HEAD")
        if after.returncode or after.stdout.strip() == before.stdout.strip():
            return False
        changed = run_git(
            "diff", "--name-only", before.stdout.strip(), after.stdout.strip()
        )
        return any(name in UPDATE_SOURCES for name in changed.stdout.split())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        log_error("update failed: %r" % error)
        return False


def send_control(port, message):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(message.encode("ascii"), ("127.0.0.1", port))
        return True
    except OSError:
        return False


def bind_control(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.bind(("127.0.0.1", port))
    return server


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HANDLE),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HANDLE),
    ]


LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class TrayIcon:
    WM_APP = 0x8000
    WM_TRAY = WM_APP + 1
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONUP = 0x0205
    WM_NULL = 0x0000
    NIM_ADD = 0x00000000
    NIM_DELETE = 0x00000002
    NIM_SETVERSION = 0x00000004
    NIF_MESSAGE = 0x00000001
    NIF_ICON = 0x00000002
    NIF_TIP = 0x00000004
    NOTIFYICON_VERSION_4 = 4
    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    LR_DEFAULTSIZE = 0x0040
    MF_STRING = 0x0000
    MF_SEPARATOR = 0x0800
    MF_BYCOMMAND = 0x0000
    MF_CHECKED = 0x0008
    MF_UNCHECKED = 0x0000
    TPM_RIGHTBUTTON = 0x0002
    TPM_RETURNCMD = 0x0100
    HWND_MESSAGE = -3

    def __init__(self, events):
        self.events = events
        self.hwnd = None
        self.icon = None
        self.data = None
        self.callback = None
        self.current_mode = DEFAULT_MODE
        self.current_on_top = True
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, self.WM_CLOSE, 0, 0)
        self.thread.join(timeout=2)

    def _add_icon(self):
        self.data = NOTIFYICONDATAW()
        self.data.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        self.data.hWnd = self.hwnd
        self.data.uID = 1
        self.data.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP
        self.data.uCallbackMessage = self.WM_TRAY
        self.data.hIcon = self.icon
        self.data.szTip = "Claude Codex Usage"
        added = ctypes.windll.shell32.Shell_NotifyIconW(
            self.NIM_ADD, ctypes.byref(self.data)
        )
        if not added:
            log_error("notification-area icon creation failed")
        self.data.uTimeoutOrVersion = self.NOTIFYICON_VERSION_4
        ctypes.windll.shell32.Shell_NotifyIconW(
            self.NIM_SETVERSION, ctypes.byref(self.data)
        )

    def _show_menu(self):
        user32 = ctypes.windll.user32
        menu = user32.CreatePopupMenu()
        for menu_id, _mode, label in MODE_MENU:
            user32.AppendMenuW(menu, self.MF_STRING, menu_id, label)
        checked = next(
            (menu_id for menu_id, mode, _ in MODE_MENU if mode == self.current_mode),
            MODE_MENU[0][0],
        )
        user32.CheckMenuRadioItem(
            menu, MODE_MENU[0][0], MODE_MENU[-1][0], checked, self.MF_BYCOMMAND
        )
        user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, self.MF_STRING, 1003, "항상 위 (Always on top)")
        user32.CheckMenuItem(
            menu,
            1003,
            self.MF_BYCOMMAND
            | (self.MF_CHECKED if self.current_on_top else self.MF_UNCHECKED),
        )
        user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, self.MF_STRING, 1001, "Show / Hide")
        user32.AppendMenuW(menu, self.MF_STRING, 1002, "Exit")
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(self.hwnd)
        command = user32.TrackPopupMenu(
            menu,
            self.TPM_RIGHTBUTTON | self.TPM_RETURNCMD,
            point.x,
            point.y,
            0,
            self.hwnd,
            None,
        )
        user32.DestroyMenu(menu)
        user32.PostMessageW(self.hwnd, self.WM_NULL, 0, 0)
        if command == 1001:
            self.events.put(("toggle", None))
        elif command == 1002:
            self.events.put(("exit", None))
        elif command == 1003:
            self.events.put(("toggle_ontop", None))
        elif command in MODE_BY_ID:
            self.events.put(("mode", MODE_BY_ID[command]))

    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = LRESULT
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_size_t,
            wintypes.LPCWSTR,
        ]
        user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.LPVOID,
        ]
        user32.TrackPopupMenu.restype = wintypes.UINT
        user32.DestroyMenu.argtypes = [wintypes.HMENU]
        shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(NOTIFYICONDATAW),
        ]
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        class_name = "ClaudeUsageTrayWindow_%d" % os.getpid()
        taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

        @WNDPROC
        def window_proc(hwnd, message, wparam, lparam):
            if message == self.WM_TRAY:
                mouse_message = int(lparam) & 0xFFFF
                if mouse_message == self.WM_LBUTTONUP:
                    self.events.put(("toggle", None))
                elif mouse_message == self.WM_RBUTTONUP:
                    self._show_menu()
                return 0
            if message == taskbar_created:
                self._add_icon()
                return 0
            if message == self.WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if message == self.WM_DESTROY:
                if self.data is not None:
                    shell32.Shell_NotifyIconW(
                        self.NIM_DELETE, ctypes.byref(self.data)
                    )
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self.callback = window_proc
        instance = kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self.callback
        window_class.hInstance = instance
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            log_error("tray window class registration failed")
            return

        self.hwnd = user32.CreateWindowExW(
            0,
            class_name,
            "Claude Codex Usage Tray",
            0,
            0,
            0,
            0,
            0,
            wintypes.HWND(self.HWND_MESSAGE),
            None,
            instance,
            None,
        )
        self.icon = user32.LoadImageW(
            None,
            str(ICON_PATH),
            self.IMAGE_ICON,
            0,
            0,
            self.LR_LOADFROMFILE | self.LR_DEFAULTSIZE,
        )
        if not self.hwnd or not self.icon:
            log_error(
                "tray creation failed hwnd=%r icon=%r error=%d"
                % (self.hwnd, self.icon, ctypes.get_last_error())
            )
            return
        self._add_icon()

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        if self.icon:
            user32.DestroyIcon(self.icon)


def rounded_rectangle(canvas, x1, y1, x2, y2, radius, **options):
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **options)


WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def work_area():
    area = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0)
    return area.left, area.top, area.right, area.bottom


def process_image_name(process_id):
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(0x1000, False, process_id)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return path.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def claude_app_window():
    """Return the visible main window of the running Claude desktop app."""
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    found = []

    @WNDENUMPROC
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        image = process_image_name(process_id.value).lower()
        if image.endswith("\\claude.exe") and "\\claude-code\\" not in image:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(visit, 0)
    return found[0] if found else 0


def claude_protocol_registered():
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Classes\claude\shell\open\command"
        ):
            return True
    except (OSError, ImportError):
        return False


def open_claude_app():
    """Show the Claude desktop app, launching it when it is not running yet."""
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        hwnd = claude_app_window()
        if hwnd:
            user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
            user32.SetForegroundWindow(hwnd)
            return
        if claude_protocol_registered():
            os.startfile("claude://")
            return
        fallback = (
            Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            / "AnthropicClaude"
            / "claude.exe"
        )
        if fallback.exists():
            subprocess.Popen(
                [str(fallback)],
                cwd=str(fallback.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
                close_fds=True,
            )
            return
        os.startfile("https://claude.ai/new")
    except Exception as error:
        log_error("opening Claude failed: %r" % error)


def open_codex_usage_page():
    """Open the official Codex usage page in the default browser."""
    try:
        os.startfile("https://chatgpt.com/codex/settings/usage")
    except Exception as error:
        log_error("opening Codex usage page failed: %r" % error)


def chatgpt_app_window():
    """Return a running ChatGPT desktop app window, preferring the normal
    ChatGPT app over ChatGPT Classic when both are open. Matches on the process
    image name (e.g. ChatGPT.exe) so a browser tab titled 'ChatGPT' is ignored.
    Returns 0 when no ChatGPT app is running.
    """
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    normal = []
    classic = []

    @WNDENUMPROC
    def visit(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) <= 0:
            return True
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        image = process_image_name(process_id.value).lower()
        if "chatgpt" in image:
            (classic if "classic" in image else normal).append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    if normal:
        return normal[0]
    if classic:
        return classic[0]
    return 0


def open_codex_target():
    """Focus a running ChatGPT / ChatGPT Classic app (ChatGPT preferred);
    when neither is running, fall back to the Codex usage page.
    """
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        hwnd = chatgpt_app_window()
        if hwnd:
            user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
            user32.SetForegroundWindow(hwnd)
            return
        open_codex_usage_page()
    except Exception as error:
        log_error("opening Codex target failed: %r" % error)
        open_codex_usage_page()


def open_source_target(key):
    if key == "codex":
        open_codex_target()
    else:
        open_claude_app()


class UsageApp:
    TRANSPARENT = "#010203"
    BACKGROUND = "#1E1E2E"
    BASE_WIDTH = 192
    PAD = 10
    ROW_TOP = 53
    ROW_STEP = 59
    ROW_BOTTOM = 50
    ERROR_HEIGHT = 96
    BUTTON_WIDTH = 24
    BUTTON_GAP = 4
    BUTTON_TOP = 8
    BUTTON_BOTTOM = 30
    GRIP = 16
    NAV_H = 24
    ARROW_WIDTH = 22
    ARROW_SPREAD = 34
    # "both_stacked" layout: each source is a labelled section of bar blocks.
    STACK_TOP = 40
    STACK_SECTION = 24
    STACK_BAR = 52
    STACK_ERROR = 28
    STACK_GAP = 22
    STACK_BOTTOM = 14
    MIN_SCALE = 0.7
    MAX_SCALE = 3.0

    def __init__(self, control_socket):
        self.control_socket = control_socket
        self.events = queue.Queue()
        settings = self._load_settings()
        self.scale = self._clamp_scale(settings.get("scale", 1.0))
        try:
            self.page = int(settings.get("page", 0)) % len(SOURCES)
        except (TypeError, ValueError):
            self.page = 0
        mode = settings.get("mode", DEFAULT_MODE)
        self.mode = mode if mode in VIEW_MODES else DEFAULT_MODE
        self.on_top = bool(settings.get("on_top", True))
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Claude Codex Usage")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.on_top)
        # Slightly translucent so the desktop shows through but text stays clear.
        self.root.attributes("-alpha", 0.85)
        try:
            self.root.attributes("-transparentcolor", self.TRANSPARENT)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(
            self.root,
            width=self.BASE_WIDTH,
            height=self.ERROR_HEIGHT,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.datas = {source["key"]: self._load_latest(source) for source in SOURCES}
        self.data = self.datas[self._source()["key"]]
        self.syncing = False
        self.user_moved = False
        self.dragging = False
        self.resizing = False
        self.drag_x = 0
        self.drag_y = 0
        self.resize_pointer = 0
        self.resize_width = self.BASE_WIDTH
        self.exiting = False
        self.restart_pending = False
        self.width = self.BASE_WIDTH
        self.height = self.ERROR_HEIGHT
        self.hit_sync = (0, 0, 0, 0)
        self.hit_close = (0, 0, 0, 0)
        self.hit_mode = (0, 0, 0, 0)
        self.hit_grip = (0, 0, 0, 0)
        self.hit_prev = (0, 0, 0, 0)
        self.hit_next = (0, 0, 0, 0)
        self.stack_regions = []
        self.bottom_anchor = None
        self.mode_var = tk.StringVar(master=self.root, value=self.mode)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Control-MouseWheel>", self._on_wheel)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._draw()
        self.root.update_idletasks()
        self._hide_from_taskbar()
        self._place()
        self.show()

        self.tray = TrayIcon(self.events)
        self.tray.current_mode = self.mode
        self.tray.current_on_top = self.on_top
        self.tray.start()
        self.listener = threading.Thread(target=self._listen, daemon=True)
        self.listener.start()
        self.root.after(100, self._poll_events)
        self.root.after(120000, self._scheduled_sync)
        self.root.after(5000, self._check_update)
        self.start_sync(False)

    def run(self):
        try:
            self.root.mainloop()
        finally:
            try:
                self.control_socket.close()
            except OSError:
                pass
            self.tray.stop()
            if self.restart_pending:
                start_main()

    def _listen(self):
        self.control_socket.settimeout(0.5)
        while not self.exiting:
            try:
                message, _ = self.control_socket.recvfrom(64)
                self.events.put((message.decode("ascii", errors="ignore"), None))
            except socket.timeout:
                continue
            except OSError:
                break

    def _poll_events(self):
        while True:
            try:
                action, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if action == "show":
                self.show()
            elif action == "toggle":
                self.toggle()
            elif action == "exit":
                self.exit()
            elif action == "restart":
                self.restart()
            elif action == "mode":
                self._set_mode(payload)
            elif action == "toggle_ontop":
                self._toggle_on_top()
            elif action == "sync_result":
                key, data = payload
                self.datas[key] = data
                if not self._stacked() and key == self._source()["key"]:
                    self.data = data
                self._draw()
                self._place()
            elif action == "sync_done":
                self.syncing = False
                self._draw()
                self._place()
        if not self.exiting:
            self.root.after(100, self._poll_events)

    def _scheduled_sync(self):
        if not self.exiting:
            self.start_sync(False)
            self.root.after(120000, self._scheduled_sync)

    def _check_update(self):
        """Look for a newer published version once, shortly after startup."""
        if self.exiting:
            return
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        if pull_updates():
            self.events.put(("restart", None))

    def start_sync(self, manual):
        if self.syncing:
            return
        self.syncing = True
        sources = self._visible_sources()
        self._draw()
        threading.Thread(
            target=self._sync_worker, args=(sources, manual), daemon=True
        ).start()

    def _sync_worker(self, sources, manual):
        # Refresh every source currently on screen, one at a time. In stacked
        # mode that is both; otherwise just the visible one, so viewing Codex
        # never launches Claude's browser sync.
        for source in sources:
            key = source["key"]
            try:
                result = run_script(source["script"], "--sync")
                if result.returncode:
                    log_error(
                        "%s sync exit=%d %s" % (key, result.returncode, result.stderr)
                    )
                data = self._load_latest(source)
                if manual and source.get("connect") and data.get("code") == "needs_login":
                    run_script(source["script"], "--connect")
                self.events.put(("sync_result", (key, data)))
            except Exception as error:
                log_error(repr(error))
                self.events.put(
                    ("sync_result", (key, {"error": "update failed (see error.log)"}))
                )
        self.events.put(("sync_done", None))

    def _source(self):
        """The single source shown in claude / codex / both_paged modes."""
        if self.mode == "claude":
            return SOURCE_BY_KEY["claude"]
        if self.mode == "codex":
            return SOURCE_BY_KEY["codex"]
        return SOURCES[self.page]

    def _stacked(self):
        return self.mode == "both_stacked"

    def _paged(self):
        return self.mode == "both_paged"

    def _visible_sources(self):
        if self._stacked():
            return list(SOURCES)
        return [self._source()]

    def _set_mode(self, mode):
        if mode not in VIEW_MODES or mode == self.mode:
            return
        self.mode = mode
        self.tray.current_mode = mode
        if not self._stacked():
            self.data = self.datas.get(self._source()["key"]) or {
                "error": "사용량 동기화 중..."
            }
        self._save_settings()
        self._draw()
        self._place()
        self.start_sync(False)

    def _toggle_on_top(self):
        self.on_top = not self.on_top
        self.tray.current_on_top = self.on_top
        try:
            self.root.attributes("-topmost", self.on_top)
        except tk.TclError:
            pass
        if self.on_top:
            self.root.lift()
        self._save_settings()

    def _load_latest(self, source=None):
        source = source or self._source()
        try:
            return json.loads(Path(source["latest"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"error": "사용량 동기화 중..."}

    def _load_settings(self):
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _clamp_scale(self, value):
        try:
            return max(self.MIN_SCALE, min(float(value), self.MAX_SCALE))
        except (TypeError, ValueError):
            return 1.0

    def _save_settings(self):
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(
                    {
                        "scale": round(self.scale, 3),
                        "page": self.page,
                        "mode": self.mode,
                        "on_top": self.on_top,
                    }
                ),
                encoding="utf-8",
            )
        except OSError as error:
            log_error(repr(error))

    def _s(self, value):
        return int(round(value * self.scale))

    def _font(self, size, weight="normal"):
        return ("Segoe UI", max(6, int(round(size * self.scale))), weight)

    def _layout_buttons(self):
        # Top-right cluster, left to right: refresh, view mode, close.
        button = self._s(self.BUTTON_WIDTH)
        gap = self._s(self.BUTTON_GAP)
        top = self._s(self.BUTTON_TOP)
        bottom = self._s(self.BUTTON_BOTTOM)
        right = self.width - self._s(self.PAD)
        self.hit_close = (right - button, top, right, bottom)
        self.hit_mode = (right - 2 * button - gap, top, right - button - gap, bottom)
        self.hit_sync = (
            right - 3 * button - 2 * gap, top, right - 2 * button - 2 * gap, bottom
        )

    def _measure(self):
        bars = (self.data.get("bars") or [])[:2]
        if bars and not self.data.get("error"):
            base_height = self.ROW_TOP + (len(bars) - 1) * self.ROW_STEP + self.ROW_BOTTOM
        else:
            base_height = self.ERROR_HEIGHT
        multi = self._paged()
        if multi:
            base_height += self.NAV_H
        self.width = self._s(self.BASE_WIDTH)
        self.height = self._s(base_height)
        self._layout_buttons()
        grip = self._s(self.GRIP)
        self.hit_grip = (
            self.width - grip,
            self.height - grip,
            self.width,
            self.height,
        )
        if multi:
            arrow = self._s(self.ARROW_WIDTH)
            spread = self._s(self.ARROW_SPREAD)
            center = self.width / 2
            nav_top = self.height - self._s(self.NAV_H) + self._s(2)
            nav_bottom = self.height - self._s(4)
            self.hit_prev = (center - spread - arrow, nav_top, center - spread, nav_bottom)
            self.hit_next = (center + spread, nav_top, center + spread + arrow, nav_bottom)
        else:
            self.hit_prev = (0, 0, 0, 0)
            self.hit_next = (0, 0, 0, 0)
        self.canvas.config(width=self.width, height=self.height)
        return bars

    def _draw_button(self, box, text):
        x1, y1, x2, y2 = box
        rounded_rectangle(
            self.canvas, x1, y1, x2, y2, self._s(4), fill="#343442", outline=""
        )
        self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            fill="#AAAAAA",
            font=self._font(9),
        )

    def _draw_grip(self):
        inset = self._s(6)
        x = self.width - inset
        y = self.height - inset
        step = max(3, self._s(4))
        for index in range(3):
            offset = index * step
            self.canvas.create_line(
                x - offset,
                y,
                x,
                y - offset,
                fill="#565666",
                width=max(1, self._s(1)),
            )

    def _draw_nav(self):
        if len(SOURCES) < 2:
            return
        for box, glyph in ((self.hit_prev, "‹"), (self.hit_next, "›")):
            x1, y1, x2, y2 = box
            self.canvas.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                text=glyph,
                fill="#AAAAAA",
                font=self._font(13, "bold"),
            )
        center_x = self.width / 2
        center_y = (self.hit_prev[1] + self.hit_prev[3]) / 2
        gap = self._s(10)
        radius = max(2, self._s(3))
        start = center_x - gap * (len(SOURCES) - 1) / 2.0
        for index in range(len(SOURCES)):
            dot_x = start + index * gap
            fill = "#EEEEEE" if index == self.page else "#565666"
            self.canvas.create_oval(
                dot_x - radius,
                center_y - radius,
                dot_x + radius,
                center_y + radius,
                fill=fill,
                outline="",
            )

    def _draw_bar(self, pad, row_y, bar):
        """Draw one usage bar (label, percent, track/fill, reset text) at row_y."""
        pct = max(0.0, min(float(bar.get("pct", 0)), 100.0))
        color = "#F1707B" if pct >= 90 else "#F5A85F" if pct >= 75 else "#4C8BF5"
        self.canvas.create_text(
            pad, row_y, text=str(bar.get("label", "")), anchor="w",
            fill="#EEEEEE", font=self._font(10, "bold"),
        )
        self.canvas.create_text(
            self.width - pad, row_y, text=str(bar.get("pct_text", "")), anchor="e",
            fill=color, font=self._font(10, "bold"),
        )
        track_top = row_y + self._s(13)
        track_bottom = row_y + self._s(21)
        self.canvas.create_rectangle(
            pad, track_top, self.width - pad, track_bottom, fill="#4A4A56", outline=""
        )
        fill_x = pad + int((self.width - 2 * pad) * pct / 100.0)
        if fill_x > pad:
            self.canvas.create_rectangle(
                pad, track_top, fill_x, track_bottom, fill=color, outline=""
            )
        self.canvas.create_text(
            pad, row_y + self._s(34), text=str(bar.get("sub", "")), anchor="w",
            fill="#999999", font=self._font(8),
        )

    def _draw_frame(self, title):
        pad = self._s(self.PAD)
        self.canvas.delete("all")
        rounded_rectangle(
            self.canvas, 1, 1, self.width - 1, self.height - 1, self._s(12),
            fill=self.BACKGROUND, outline="#3B3B48",
        )
        self.canvas.create_text(
            pad, self._s(19), text=title, anchor="w",
            fill="#888899", font=self._font(8, "bold"),
        )
        self._draw_button(self.hit_sync, "..." if self.syncing else "↻")
        self._draw_button(self.hit_mode, "▾")
        self._draw_button(self.hit_close, "×")
        self._draw_grip()

    def _draw(self):
        if self._stacked():
            self._draw_stacked()
            return
        bars = self._measure()
        pad = self._s(self.PAD)
        self._draw_frame(self._source()["title"])
        if self._paged():
            self._draw_nav()

        if self.data.get("error") or not bars:
            self.canvas.create_text(
                pad,
                self._s(52),
                text=str(self.data.get("error") or "공식 사용량 동기화 중..."),
                anchor="w",
                fill="#F1707B",
                width=self.width - 2 * pad,
                font=self._font(9),
            )
            return

        for index, bar in enumerate(bars):
            self._draw_bar(pad, self._s(self.ROW_TOP + index * self.ROW_STEP), bar)

    def _measure_stacked(self):
        self.width = self._s(self.BASE_WIDTH)
        height = self.STACK_TOP
        for index, source in enumerate(SOURCES):
            if index:
                height += self.STACK_GAP
            height += self.STACK_SECTION
            data = self.datas.get(source["key"]) or {}
            bars = (data.get("bars") or [])[:2]
            if bars and not data.get("error"):
                height += self.STACK_BAR * len(bars)
            else:
                height += self.STACK_ERROR
        height += self.STACK_BOTTOM
        self.height = self._s(height)
        self._layout_buttons()
        grip = self._s(self.GRIP)
        self.hit_grip = (self.width - grip, self.height - grip, self.width, self.height)
        self.hit_prev = (0, 0, 0, 0)
        self.hit_next = (0, 0, 0, 0)
        self.canvas.config(width=self.width, height=self.height)

    def _draw_stacked(self):
        self._measure_stacked()
        pad = self._s(self.PAD)
        self._draw_frame("USAGE")
        self.stack_regions = []
        row = self.STACK_TOP
        for index, source in enumerate(SOURCES):
            if index:
                row += self.STACK_GAP
            self.canvas.create_text(
                pad, self._s(row + 9), text=source["title"].split()[0], anchor="w",
                fill="#888899", font=self._font(8, "bold"),
            )
            row += self.STACK_SECTION
            data = self.datas.get(source["key"]) or {}
            bars = (data.get("bars") or [])[:2]
            if bars and not data.get("error"):
                for bar in bars:
                    self._draw_bar(pad, self._s(row + 10), bar)
                    row += self.STACK_BAR
            else:
                self.canvas.create_text(
                    pad, self._s(row + 6),
                    text=str(data.get("error") or "동기화 중..."),
                    anchor="w", fill="#F1707B", width=self.width - 2 * pad,
                    font=self._font(9),
                )
                row += self.STACK_ERROR
            # Double-click boundary: this source owns everything above this y.
            self.stack_regions.append((source["key"], self._s(row)))

    @staticmethod
    def _contains(box, x, y):
        return box[0] <= x <= box[2] and box[1] <= y <= box[3]

    def _on_control(self, x, y):
        return (
            self._contains(self.hit_sync, x, y)
            or self._contains(self.hit_mode, x, y)
            or self._contains(self.hit_close, x, y)
            or self._contains(self.hit_grip, x, y)
            or self._contains(self.hit_prev, x, y)
            or self._contains(self.hit_next, x, y)
        )

    def _change_page(self, delta):
        count = len(SOURCES)
        if count < 2:
            return
        new_page = (self.page + delta) % count
        if new_page == self.page:
            return
        self.page = new_page
        # Show the newly selected page's cached numbers immediately, then
        # refresh only that page in the background so flipping never launches
        # the other source's sync (e.g. Claude's browser).
        self.data = self.datas.get(self._source()["key"]) or {
            "error": "사용량 동기화 중..."
        }
        self._save_settings()
        self._draw()
        self._place()
        self.start_sync(False)

    def _on_click(self, event):
        if self._contains(self.hit_grip, event.x, event.y):
            self.resizing = True
            self.resize_pointer = self.root.winfo_pointerx()
            self.resize_width = self.width
            return
        if self._paged() and self._contains(self.hit_prev, event.x, event.y):
            self._change_page(-1)
            return
        if self._paged() and self._contains(self.hit_next, event.x, event.y):
            self._change_page(1)
            return
        if self._contains(self.hit_sync, event.x, event.y):
            self.start_sync(True)
            return
        if self._contains(self.hit_mode, event.x, event.y):
            self._show_mode_menu()
            return
        if self._contains(self.hit_close, event.x, event.y):
            self.hide()
            return
        self.dragging = True
        self.drag_x = event.x
        self.drag_y = event.y

    def _double_click_target(self, y):
        """Which source a double-click opens, given the click's y position."""
        if self.mode == "claude":
            return "claude"
        if self.mode == "codex":
            return "codex"
        if self._paged():
            return self._source()["key"]
        # Stacked: pick the section the click falls in (title area -> first).
        for key, region_bottom in self.stack_regions:
            if y < region_bottom:
                return key
        if self.stack_regions:
            return self.stack_regions[-1][0]
        return "claude"

    def _on_double_click(self, event):
        if self._on_control(event.x, event.y):
            return
        self.dragging = False
        open_source_target(self._double_click_target(event.y))

    def _show_mode_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        self.mode_var.set(self.mode)
        for _menu_id, key, label in MODE_MENU:
            menu.add_radiobutton(
                label=label,
                value=key,
                variable=self.mode_var,
                command=lambda k=key: self._set_mode(k),
            )
        x = self.root.winfo_rootx() + int((self.hit_mode[0] + self.hit_mode[2]) / 2)
        y = self.root.winfo_rooty() + int(self.hit_mode[3])
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _on_drag(self, event):
        if self.resizing:
            delta = self.root.winfo_pointerx() - self.resize_pointer
            self._apply_scale((self.resize_width + delta) / float(self.BASE_WIDTH))
            return
        if not self.dragging:
            return
        self.user_moved = True
        x = self.root.winfo_pointerx() - self.drag_x
        y = self.root.winfo_pointery() - self.drag_y
        self.root.geometry("+%d+%d" % (x, y))

    def _on_release(self, _event):
        if self.resizing:
            self.resizing = False
            self._save_settings()
        if self.dragging:
            # Remember the new bottom edge so later resizes keep it in place.
            self.bottom_anchor = self.root.winfo_y() + self.height
        self.dragging = False

    def _on_wheel(self, event):
        self._apply_scale(self.scale + (0.1 if event.delta > 0 else -0.1))
        self._save_settings()

    def _apply_scale(self, value):
        value = max(self.MIN_SCALE, min(round(value, 3), self.MAX_SCALE))
        if abs(value - self.scale) < 0.005:
            return
        self.scale = value
        self._draw()
        self._place()

    def _place(self):
        left, top, right, bottom = work_area()
        if self.user_moved:
            # Keep the bottom edge where it is, so a taller/shorter window grows
            # or shrinks upward instead of dragging the whole widget down.
            x = self.root.winfo_x()
            if self.bottom_anchor is not None:
                y = self.bottom_anchor - self.height
            else:
                y = self.root.winfo_y()
        else:
            x = right - self.width - 14
            y = bottom - self.height - 8
        x = max(left, min(x, right - self.width))
        y = max(top, min(y, bottom - self.height))
        self.root.geometry("%dx%d+%d+%d" % (self.width, self.height, x, y))
        self.bottom_anchor = y + self.height

    def _hide_from_taskbar(self):
        self.root.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = wintypes.LONG
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        user32.SetWindowLongW.restype = wintypes.LONG
        hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        ex_style = user32.GetWindowLongW(hwnd, -20)
        ex_style = (ex_style | 0x00000080) & ~0x00040000
        user32.SetWindowLongW(hwnd, -20, ex_style)

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", self.on_top)

    def hide(self):
        self.root.withdraw()

    def toggle(self):
        if self.root.state() == "withdrawn":
            self.show()
        else:
            self.hide()

    def restart(self):
        """Reload the widget after an update, staying armed for Claude Code."""
        if self.exiting:
            return
        self.exiting = True
        self.restart_pending = True
        self.root.destroy()

    def exit(self):
        if self.exiting:
            return
        self.exiting = True
        try:
            AUTO_FILE.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            log_error(repr(error))
        try:
            run_usage("--close", timeout=20)
        except Exception as error:
            log_error(repr(error))
        self.root.destroy()


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


def claude_code_process_ids():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    ]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return set()
    result = set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            if entry.szExeFile.lower() == "claude.exe":
                handle = kernel32.OpenProcess(0x1000, False, entry.th32ProcessID)
                if handle:
                    try:
                        size = wintypes.DWORD(32768)
                        path = ctypes.create_unicode_buffer(size.value)
                        if kernel32.QueryFullProcessImageNameW(
                            handle, 0, path, ctypes.byref(size)
                        ) and "\\windowsapps\\claude_" not in path.value.lower():
                            result.add(int(entry.th32ProcessID))
                    finally:
                        kernel32.CloseHandle(handle)
            success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return result


def start_main():
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(BASE_DIR),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
    )


def run_watcher():
    try:
        control = bind_control(WATCH_PORT)
    except OSError:
        return 0
    control.settimeout(2)
    known = set()
    try:
        while True:
            current = claude_code_process_ids()
            if any(process_id not in known for process_id in current) and AUTO_FILE.exists():
                start_main()
            known = current
            try:
                message, _ = control.recvfrom(64)
                if message.decode("ascii", errors="ignore") == "exit":
                    break
            except socket.timeout:
                pass
    finally:
        control.close()
    return 0


def uninstall():
    send_control(MAIN_PORT, "exit")
    send_control(WATCH_PORT, "exit")
    time.sleep(0.2)
    for path in (STARTUP_LINK, DESKTOP_LINK, LEGACY_DESKTOP_LINK):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            log_error(repr(error))
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "Claude Codex Usage",
        "자동 실행과 바탕화면 바로가기를 제거했습니다.\n로그인 및 사용량 데이터는 보존됩니다.",
    )
    root.destroy()


def main():
    if "--watch" in sys.argv:
        return run_watcher()
    if "--uninstall" in sys.argv:
        uninstall()
        return 0
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        AUTO_FILE.write_text("enabled", encoding="utf-8")
    except OSError as error:
        log_error(repr(error))
    try:
        control = bind_control(MAIN_PORT)
    except OSError:
        send_control(MAIN_PORT, "show")
        return 0
    UsageApp(control).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
