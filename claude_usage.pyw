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
from tkinter import font as tkfont
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
UPDATE_SOURCES = ("claude_usage.pyw", "usage.py", "codex_usage.py", "install.py", "install.cmd")
CONTROL_ACTIONS = {message.encode("ascii"): message for message in ("show", "hide", "toggle", "exit")}

# The Claude and ChatGPT desktop apps are Microsoft Store (MSIX) packages under
# a protected WindowsApps folder, so they cannot be launched by their exe path.
# They launch by AppUserModelID via "explorer shell:AppsFolder\<AUMID>". Their
# package family names are stable across versions.
CLAUDE_AUMID = "Claude_pzs8sxrjxfjjc!Claude"
CHATGPT_AUMID = "OpenAI.Codex_2p2nqsd0c76g0!App"
CLAUDE_SITE = "https://claude.ai/new"
CODEX_SITE = "https://chatgpt.com/codex/settings/usage"
# Opened in the browser when the user clicks the "update needed" badge.
REPO_URL = "https://github.com/minsk8775/claude-codex-usage"
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
#   auto         - follow which apps are running: one open -> that one only,
#                  both open -> both stacked (default)
#   both_stacked - both sources at once, stacked in one window
#   both_paged   - both sources, one per page, flipped with the on-screen arrows
#   claude       - Claude only
#   codex        - Codex only
VIEW_MODES = ("auto", "both_stacked", "both_paged", "claude", "codex")
DEFAULT_MODE = "auto"
# (menu id, mode key, string key) rendered in the tray menu, in this order.
MODE_MENU = (
    (2000, "auto", "mode_auto"),
    (2001, "claude", "mode_claude"),
    (2002, "codex", "mode_codex"),
    (2003, "both_stacked", "mode_both_stacked"),
    (2004, "both_paged", "mode_both_paged"),
)
MODE_BY_ID = {menu_id: mode for menu_id, mode, _key in MODE_MENU}
LANG_KO_ID = 3000
LANG_EN_ID = 3001

# UI language. The widget chrome, the update badge and the two reader scripts
# (via a --lang flag) all follow this. Default Korean; switch in the right-click
# / notification-icon menu. Claude's own reset text is scraped from its page and
# follows Claude's account language.
LANGS = ("ko", "en")
DEFAULT_LANG = "ko"
STRINGS = {
    "syncing": {"ko": "사용량 동기화 중...", "en": "Syncing usage..."},
    "syncing_official": {"ko": "공식 사용량 동기화 중...", "en": "Syncing official usage..."},
    "update_full": {"ko": "● 업데이트 필요", "en": "● Update available"},
    "update_short": {"ko": "● 업데이트", "en": "● Update"},
    "mode_auto": {"ko": "자동 (앱에 맞춰)", "en": "Auto (follow apps)"},
    "mode_claude": {"ko": "Claude만 보기", "en": "Claude only"},
    "mode_codex": {"ko": "Codex만 보기", "en": "Codex only"},
    "mode_both_stacked": {"ko": "둘 다 보기", "en": "Both (stacked)"},
    "mode_both_paged": {"ko": "둘 다 (좌우 전환)", "en": "Both (arrows)"},
    "always_on_top": {"ko": "항상 위 (Always on top)", "en": "Always on top"},
    "show_hide": {"ko": "표시 / 숨기기", "en": "Show / Hide"},
    "exit": {"ko": "종료", "en": "Exit"},
    "language": {"ko": "언어 (Language)", "en": "Language"},
    "lang_ko": {"ko": "한국어", "en": "한국어 (Korean)"},
    "lang_en": {"ko": "영어 (English)", "en": "English"},
}


def tr(lang, key):
    """Translate a UI string key for the given language, falling back to Korean."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get(DEFAULT_LANG) or key
# Process-name substring -> usage source key, for the auto view (see above).
APP_KEY_BY_NAME = (("claude", "claude"), ("chatgpt", "codex"))


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


# The widget never auto-installs updates. It only *checks* the project's own
# GitHub repository over HTTPS and, when newer code exists, shows a badge the
# user clicks to review and install it themselves. Checking is limited to the
# trusted origin so a repointed "origin" cannot even prompt an update, and the
# check is read-only (fetch, never checkout), so no downloaded code is executed.
# (Case-insensitive; the .git suffix is optional.)
ALLOWED_ORIGINS = ("https://github.com/minsk8775/claude-codex-usage",)
NO_UPDATE_FILE = BASE_DIR / ".noupdate"


def update_checks_allowed():
    """False when update checks are disabled or origin is not the trusted repo."""
    if os.environ.get("CLAUDE_CODEX_NO_UPDATE") or NO_UPDATE_FILE.exists():
        return False
    origin = run_git("remote", "get-url", "origin")
    if origin.returncode:
        return False
    url = origin.stdout.strip().lower()
    if url.endswith(".git"):
        url = url[:-4]
    return url in ALLOWED_ORIGINS


def updates_available():
    """True when the trusted origin has newer widget code than this checkout.

    Read-only: it fetches remote refs but never checks anything out, so no
    downloaded code runs here. The user applies the update manually after
    reviewing it on GitHub.
    """
    if not (BASE_DIR / ".git").exists():
        return False
    try:
        if not update_checks_allowed():
            return False
        fetched = run_git("fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", "main")
        if fetched.returncode:
            log_error("update check skipped: %s" % (fetched.stderr or "").strip())
            return False
        head = run_git("rev-parse", "HEAD")
        upstream = run_git("rev-parse", "FETCH_HEAD")
        if head.returncode or upstream.returncode:
            return False
        if head.stdout.strip() == upstream.stdout.strip():
            return False
        if run_git("merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD").returncode:
            return False
        # Only flag when tracked source files differ, so a docs-only commit on
        # the remote does not nag the user to update.
        changed = run_git("diff", "--name-only", "HEAD", "FETCH_HEAD", "--", *UPDATE_SOURCES)
        if changed.returncode:
            return False
        return any(name in UPDATE_SOURCES for name in changed.stdout.split())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        log_error("update check failed: %r" % error)
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
    MF_POPUP = 0x0010
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
        self.current_lang = DEFAULT_LANG
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
        lang = self.current_lang
        menu = user32.CreatePopupMenu()
        for menu_id, _mode, key in MODE_MENU:
            user32.AppendMenuW(menu, self.MF_STRING, menu_id, tr(lang, key))
        checked = next(
            (menu_id for menu_id, mode, _ in MODE_MENU if mode == self.current_mode),
            MODE_MENU[0][0],
        )
        user32.CheckMenuRadioItem(
            menu, MODE_MENU[0][0], MODE_MENU[-1][0], checked, self.MF_BYCOMMAND
        )
        user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, self.MF_STRING, 1003, tr(lang, "always_on_top"))
        user32.CheckMenuItem(
            menu,
            1003,
            self.MF_BYCOMMAND
            | (self.MF_CHECKED if self.current_on_top else self.MF_UNCHECKED),
        )
        # Language submenu (Korean / English) as a radio group.
        lang_menu = user32.CreatePopupMenu()
        user32.AppendMenuW(lang_menu, self.MF_STRING, LANG_KO_ID, tr(lang, "lang_ko"))
        user32.AppendMenuW(lang_menu, self.MF_STRING, LANG_EN_ID, tr(lang, "lang_en"))
        user32.CheckMenuRadioItem(
            lang_menu, LANG_KO_ID, LANG_EN_ID,
            LANG_EN_ID if lang == "en" else LANG_KO_ID, self.MF_BYCOMMAND,
        )
        user32.AppendMenuW(menu, self.MF_POPUP, lang_menu, tr(lang, "language"))
        user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, self.MF_STRING, 1001, tr(lang, "show_hide"))
        user32.AppendMenuW(menu, self.MF_STRING, 1002, tr(lang, "exit"))
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
        elif command == LANG_KO_ID:
            self.events.put(("lang", "ko"))
        elif command == LANG_EN_ID:
            self.events.put(("lang", "en"))
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


def focus_window(hwnd):
    """Restore (if minimised) and bring a top-level window to the foreground."""
    user32 = ctypes.windll.user32
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
    user32.SetForegroundWindow(hwnd)


def launch_aumid(aumid):
    """Launch a Store/desktop app by its AppUserModelID via the shell."""
    try:
        subprocess.Popen(
            ["explorer.exe", "shell:AppsFolder\\" + aumid],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True
    except OSError as error:
        log_error("launch %s failed: %r" % (aumid, error))
        return False


def get_installed_aumids():
    """Return the AppUserModelIDs of installed Start-menu apps (Store + desktop).

    Used to decide whether to launch an app or fall back to its website. Returns
    an empty set on any failure, which callers treat as 'unknown' (try the app).
    """
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Get-StartApps | Select-Object -ExpandProperty AppID",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=20,
            check=False,
        )
        return {line.strip() for line in (result.stdout or "").splitlines() if line.strip()}
    except (OSError, subprocess.SubprocessError) as error:
        log_error("Get-StartApps failed: %r" % error)
        return set()


def open_app_or_site(window_fn, aumid, site, installed):
    """Bring up a desktop app: focus its running window, else launch it by
    AUMID, else open its website. The site is used only when the app is known
    not to be installed; if install state is unknown we still try the app.
    """
    try:
        hwnd = window_fn()
        if hwnd:
            focus_window(hwnd)
            return
        if (not installed or aumid in installed) and launch_aumid(aumid):
            return
        os.startfile(site)
    except Exception as error:
        log_error("opening app failed: %r" % error)
        try:
            os.startfile(site)
        except OSError:
            pass


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
        self.events = queue.Queue(maxsize=256)
        settings = self._load_settings()
        self.scale = self._clamp_scale(settings.get("scale", 1.0))
        try:
            self.page = int(settings.get("page", 0)) % len(SOURCES)
        except (TypeError, ValueError):
            self.page = 0
        mode = settings.get("mode", DEFAULT_MODE)
        self.mode = mode if mode in VIEW_MODES else DEFAULT_MODE
        lang = settings.get("lang", DEFAULT_LANG)
        self.lang = lang if lang in LANGS else DEFAULT_LANG
        self.on_top = bool(settings.get("on_top", True))
        self.app_ids = set()  # installed app AUMIDs; filled in the background
        self.auto_view = "both_stacked"  # effective view when mode == "auto"
        self._known_app_keys = set()
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
        self.pending_sync = None
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
        self.hit_update = (0, 0, 0, 0)
        self.update_available = False
        self.stack_regions = []
        self.bottom_anchor = None
        self.mode_var = tk.StringVar(master=self.root, value=self.mode)
        self.on_top_var = tk.BooleanVar(master=self.root, value=self.on_top)
        self.lang_var = tk.StringVar(master=self.root, value=self.lang)
        try:
            self._known_app_keys = running_app_keys()
        except Exception:
            self._known_app_keys = set()
        if self.mode == "auto":
            self.auto_view = self._auto_view_for(self._known_app_keys)
        # Keep self.data aligned with the (possibly auto-chosen) single source.
        self.data = self.datas.get(self._source()["key"], self.data)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Control-MouseWheel>", self._on_wheel)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._draw()
        self.root.update_idletasks()
        self._hide_from_taskbar()
        self._place()
        # In auto mode with no watched app running, start hidden; the widget
        # reappears when Claude or ChatGPT opens.
        if self.mode == "auto" and not self._known_app_keys:
            self.root.withdraw()
        else:
            self.show()

        self.tray = TrayIcon(self.events)
        self.tray.current_mode = self.mode
        self.tray.current_on_top = self.on_top
        self.tray.current_lang = self.lang
        self.tray.start()
        self.listener = threading.Thread(target=self._listen, daemon=True)
        self.listener.start()
        self.root.after(100, self._poll_events)
        self.root.after(120000, self._scheduled_sync)
        self.root.after(5000, self._check_update)
        self.root.after(1500, self._auto_tick)
        threading.Thread(target=self._load_installed_apps, daemon=True).start()
        self.start_sync(False)

    def _auto_tick(self):
        """Follow running apps: switch the auto view, and reveal a hidden widget
        when a watched app has just launched."""
        if self.exiting:
            return
        try:
            keys = running_app_keys()
        except Exception:
            keys = set()
        if self.mode == "auto":
            view = self._auto_view_for(keys)
            if view != self.auto_view:
                self.auto_view = view
                if not self._stacked():
                    self.data = self.datas.get(self._source()["key"]) or {
                        "error": self._t("syncing")
                    }
                self._draw()
                self._place()
                self.start_sync(False)
            # The window follows the apps: it appears when one is running and
            # hides when both are closed; reopening an app brings it back.
            if (keys - self._known_app_keys) and self.root.state() == "withdrawn":
                self.show()
            elif not keys and self.root.state() != "withdrawn":
                self.hide()
        elif (keys - self._known_app_keys) and self.root.state() == "withdrawn":
            self.show()
        self._known_app_keys = keys
        if not self.exiting:
            self.root.after(3000, self._auto_tick)

    def _load_installed_apps(self):
        # Cache which apps are installed so double-click can choose app vs site
        # without running PowerShell on every click.
        self.app_ids = get_installed_aumids()

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
                message, _ = self.control_socket.recvfrom(65)
                action = CONTROL_ACTIONS.get(message)
                if action is not None:
                    try:
                        self.events.put_nowait((action, None))
                    except queue.Full:
                        pass
            except socket.timeout:
                continue
            except OSError as error:
                if getattr(error, "winerror", None) == 10040:  # oversized UDP datagram
                    continue
                break

    def _poll_events(self):
        for _ in range(64):
            try:
                action, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if action == "show":
                self.show()
            elif action == "hide":
                self.hide()
            elif action == "toggle":
                self.toggle()
            elif action == "exit":
                self.exit()
                return
            elif action == "restart":
                self.restart()
                return
            elif action == "update_found":
                self.update_available = True
                self._draw()
                self._place()
            elif action == "mode":
                self._set_mode(payload)
            elif action == "lang":
                self._set_lang(payload)
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
                if self.pending_sync is not None:
                    manual, self.pending_sync = self.pending_sync, None
                    self.start_sync(manual)
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
        # Notify only. We never auto-install; the badge lets the user review and
        # apply the update on GitHub themselves.
        if updates_available():
            self.events.put(("update_found", None))

    def start_sync(self, manual):
        if self.exiting:
            return
        if self.syncing:
            self.pending_sync = bool(manual or self.pending_sync)
            return
        self.syncing = True
        sources = self._visible_sources()
        self._draw()
        threading.Thread(
            target=self._sync_worker, args=(sources, manual, self.lang), daemon=True
        ).start()

    def _sync_worker(self, sources, manual, lang):
        # Refresh every source currently on screen, one at a time. In stacked
        # mode that is both; otherwise just the visible one, so viewing Codex
        # never launches Claude's browser sync.
        for source in sources:
            if self.exiting:
                break
            key = source["key"]
            try:
                result = run_script(source["script"], "--sync", "--lang", lang)
                if result.returncode:
                    log_error(
                        "%s sync exit=%d %s" % (key, result.returncode, result.stderr)
                    )
                    raise RuntimeError("%s reader failed" % key)
                data = self._load_latest(source)
                if manual and source.get("connect") and data.get("code") == "needs_login":
                    run_script(source["script"], "--connect", "--lang", lang)
                self.events.put(("sync_result", (key, data)))
            except Exception as error:
                log_error(repr(error))
                self.events.put(
                    ("sync_result", (key, {"error": "update failed (see error.log)"}))
                )
        self.events.put(("sync_done", None))

    def _effective_mode(self):
        """The concrete view in effect. In auto mode it follows running apps."""
        if self.mode == "auto":
            return self.auto_view
        return self.mode

    def _source(self):
        """The single source shown in claude / codex / both_paged modes."""
        mode = self._effective_mode()
        if mode == "claude":
            return SOURCE_BY_KEY["claude"]
        if mode == "codex":
            return SOURCE_BY_KEY["codex"]
        return SOURCES[self.page]

    def _stacked(self):
        return self._effective_mode() == "both_stacked"

    def _paged(self):
        return self._effective_mode() == "both_paged"

    @staticmethod
    def _auto_view_for(keys):
        if keys == {"claude"}:
            return "claude"
        if keys == {"codex"}:
            return "codex"
        return "both_stacked"

    def _desired_auto_view(self):
        """Auto view based on which desktop apps are running."""
        try:
            keys = running_app_keys()
        except Exception:
            keys = set()
        return self._auto_view_for(keys)

    def _visible_sources(self):
        if self._stacked():
            return list(SOURCES)
        return [self._source()]

    def _t(self, key):
        return tr(self.lang, key)

    def _set_mode(self, mode):
        if mode not in VIEW_MODES or mode == self.mode:
            return
        self.mode = mode
        self.tray.current_mode = mode
        if mode == "auto":
            self.auto_view = self._desired_auto_view()
        if not self._stacked():
            self.data = self.datas.get(self._source()["key"]) or {
                "error": self._t("syncing")
            }
        self._save_settings()
        self._draw()
        self._place()
        self.start_sync(False)

    def _set_lang(self, lang):
        if lang not in LANGS or lang == self.lang:
            return
        self.lang = lang
        self.tray.current_lang = lang
        self.lang_var.set(lang)
        self._save_settings()
        self._draw()
        self._place()
        # Re-sync so the reader scripts regenerate their labels in the new
        # language (Claude session/all-models, Codex windows and reset text).
        self.start_sync(False)

    def _toggle_on_top(self):
        self.on_top = not self.on_top
        self.tray.current_on_top = self.on_top
        self.on_top_var.set(self.on_top)
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
            data = json.loads(Path(source["latest"]).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {"error": self._t("syncing")}

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
                        "lang": self.lang,
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
        if bar.get("stale"):
            color = "#999999"
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
        self._draw_update_badge(title)
        self._draw_grip()

    def _draw_update_badge(self, title):
        """When newer code exists upstream, show a clickable badge in the header
        between the title and the buttons. Clicking it opens the repo on GitHub
        so the user can review and install the update themselves.
        """
        self.hit_update = (0, 0, 0, 0)
        if not self.update_available:
            return
        pad = self._s(self.PAD)
        font = self._font(8, "bold")
        try:
            measure = tkfont.Font(root=self.root, font=font).measure
        except Exception:
            return
        gap = self._s(self.BUTTON_GAP)
        right_edge = self.hit_sync[0] - gap
        left_bound = pad + measure(title) + self._s(8)
        avail = right_edge - left_bound
        # Widest label that fits the free header space; the dot always fits.
        text = "●"
        for candidate in (self._t("update_full"), self._t("update_short"), "●"):
            if measure(candidate) <= avail or candidate == "●":
                text = candidate
                break
        width = measure(text)
        self.canvas.create_text(
            right_edge, self._s(19), text=text, anchor="e",
            fill="#F1707B", font=font,
        )
        # Clickable box with a little slack around the glyphs.
        self.hit_update = (
            right_edge - width - self._s(4),
            self._s(self.BUTTON_TOP),
            right_edge + self._s(3),
            self._s(self.BUTTON_BOTTOM),
        )

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
                text=str(self.data.get("error") or self._t("syncing_official")),
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
                    text=str(data.get("error") or self._t("syncing")),
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
            or self._contains(self.hit_update, x, y)
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
            "error": self._t("syncing")
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
        if self._contains(self.hit_update, event.x, event.y):
            self._open_update_page()
            return
        if self._contains(self.hit_sync, event.x, event.y):
            self.start_sync(True)
            return
        if self._contains(self.hit_mode, event.x, event.y):
            self._show_context_menu(
                self.root.winfo_rootx() + (self.hit_mode[0] + self.hit_mode[2]) / 2,
                self.root.winfo_rooty() + self.hit_mode[3],
            )
            return
        if self._contains(self.hit_close, event.x, event.y):
            self.hide()
            return
        self.dragging = True
        self.drag_x = event.x
        self.drag_y = event.y

    def _double_click_target(self, y):
        """Which source a double-click opens, given the click's y position."""
        mode = self._effective_mode()
        if mode == "claude":
            return "claude"
        if mode == "codex":
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

    def _open_update_page(self):
        """Open the project on GitHub so the user can review and install the
        update. We never install it for them from here."""
        try:
            os.startfile(REPO_URL)
        except OSError as error:
            log_error("opening update page failed: %r" % error)

    def _open_source(self, key):
        if key == "codex":
            open_app_or_site(
                chatgpt_app_window, CHATGPT_AUMID, CODEX_SITE, self.app_ids
            )
        else:
            open_app_or_site(
                claude_app_window, CLAUDE_AUMID, CLAUDE_SITE, self.app_ids
            )

    def _on_double_click(self, event):
        if self._on_control(event.x, event.y):
            return
        self.dragging = False
        self._open_source(self._double_click_target(event.y))

    def _show_context_menu(self, x=None, y=None):
        """The same menu the notification-area icon shows: view modes, always on
        top, show/hide, exit."""
        menu = tk.Menu(self.root, tearoff=0)
        self.mode_var.set(self.mode)
        for _menu_id, key, string_key in MODE_MENU:
            menu.add_radiobutton(
                label=self._t(string_key),
                value=key,
                variable=self.mode_var,
                command=lambda k=key: self._set_mode(k),
            )
        menu.add_separator()
        self.on_top_var.set(self.on_top)
        menu.add_checkbutton(
            label=self._t("always_on_top"),
            variable=self.on_top_var,
            command=self._toggle_on_top,
        )
        # Language submenu (Korean / English).
        self.lang_var.set(self.lang)
        lang_menu = tk.Menu(menu, tearoff=0)
        for code, string_key in (("ko", "lang_ko"), ("en", "lang_en")):
            lang_menu.add_radiobutton(
                label=self._t(string_key),
                value=code,
                variable=self.lang_var,
                command=lambda c=code: self._set_lang(c),
            )
        menu.add_cascade(label=self._t("language"), menu=lang_menu)
        menu.add_separator()
        menu.add_command(label=self._t("show_hide"), command=self.toggle)
        menu.add_command(label=self._t("exit"), command=self.exit)
        if x is None:
            x = self.root.winfo_pointerx()
            y = self.root.winfo_pointery()
        try:
            menu.tk_popup(int(x), int(y))
        finally:
            menu.grab_release()

    def _on_right_click(self, _event):
        self._show_context_menu()

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


def running_app_keys():
    """Return the source keys ('claude'/'codex') whose desktop app is running.

    Used by the auto view to show only the app(s) currently open.
    """
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return set()
    keys = set()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while success:
            name = entry.szExeFile.lower()
            for app, key in APP_KEY_BY_NAME:
                if app in name:
                    keys.add(key)
            success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return keys


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
    # Retry the bind for a few seconds: when install.cmd restarts the watcher it
    # first tells the old one to exit, and the port can take a moment to free.
    control = None
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            control = bind_control(WATCH_PORT)
            break
        except OSError:
            time.sleep(0.5)
    if control is None:
        return 0
    control.settimeout(2)
    known = set()
    try:
        while True:
            current = running_app_keys()
            if (current - known) and AUTO_FILE.exists():
                start_main()
            known = current
            try:
                message, _ = control.recvfrom(65)
                if message == b"exit":
                    break
            except socket.timeout:
                pass
            except OSError as error:
                if getattr(error, "winerror", None) != 10040:
                    raise
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
