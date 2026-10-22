"""Usage badges pinned to the Claude and Codex app windows' title bars.

The widget starts this as a small helper process when its display mode includes
title-bar badges ("badges only" or "widget + badges"). Each badge is a tiny window *owned* by the app window, so it sits
just above that window's title bar, follows it when moved, is covered along with
it, and hides when the app is minimized. It only reads the caches the readers
already write (latest.json / codex_latest.json); it never reads cookies, tokens
or anything from the apps themselves.

It runs as its own DPI-aware process so badge positions match the app windows on
scaled (125%/150%) displays, and exits on its own when the widget that started
it is gone.

    title_badges.py --parent <widget pid>
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
STATE_DIR = LOCAL / "ClaudeCodexUsage"
SETTINGS_FILE = STATE_DIR / "settings.json"
POSITIONS_FILE = STATE_DIR / "badge_positions.json"
MAIN_PORT = 47671          # widget control port ("show")
BADGE_PORT = 47673         # single-instance lock for this helper

APPS = (
    # key, process-image keywords, cache file
    ("claude", ("claude",), "latest.json"),
    ("codex", ("codex", "chatgpt"), "codex_latest.json"),
)

# Layout, in 100%-scale pixels (multiplied by the app window's DPI scale).
TITLE_BAR = 40          # app title-bar height the badge is centred in
BUTTONS = 150           # room kept free for the app's own –/□/× buttons
PAD_X = 9
PAD_Y = 3
COL_GAP = 14
MIN_COL = 58

BG = "#1E1E2E"
BORDER = "#3B3B48"
TRACK = "#3A3A48"
DIM = "#9A9AAA"
FAINT = "#7E7E8E"
WARN = "#F1707B"
TRANSPARENT = "#010203"

STRINGS = {
    "session": {"ko": "세션", "en": "Session"},
    "weekly": {"ko": "주간", "en": "Weekly"},
    "soon": {"ko": "곧 초기화", "en": "resets soon"},
    "stale": {"ko": "오래된 기록", "en": "stale"},
    "syncing": {"ko": "동기화 중…", "en": "Syncing…"},
    "login": {"ko": "로그인 필요", "en": "Sign-in needed"},
    "failed": {"ko": "동기화 실패", "en": "Sync failed"},
    "reset_pos": {"ko": "배지 위치 초기화", "en": "Reset badge position"},
    "open_widget": {"ko": "위젯 열기", "en": "Open widget"},
}


def tr(lang, key):
    entry = STRINGS[key]
    return entry.get(lang) or entry["ko"]


# --------------------------------------------------------------------------- #
# Pure helpers (no Windows calls; covered by tests)
# --------------------------------------------------------------------------- #

def level_color(pct, stale):
    if stale or pct is None:
        return "#999999"
    if pct >= 90:
        return "#F1707B"
    if pct >= 75:
        return "#F5A85F"
    return "#4C8BF5"


def short_label(label, lang="ko", hint=""):
    """'현재 세션 · Spark' -> '세션·Spark', '모든 모델' -> '주간', etc."""
    text = str(label or "")
    head, _, tag = text.partition("·")
    low = head.lower()
    hint = str(hint or "")
    if "세션" in head or "session" in low or "5시간" in head or "5-hour" in low or "5 hour" in low:
        base = tr(lang, "session")
    elif any(word in head for word in ("모든 모델", "주간")) or any(
            word in low for word in ("all models", "week")):
        base = tr(lang, "weekly")
    elif _GENERIC.match(head) and ("주간" in hint or "week" in hint.lower()):
        # The Codex page sometimes gives only "사용 한도"; its reset line names the window.
        base = tr(lang, "weekly")
    elif _GENERIC.match(head) and ("5시간" in hint or "5-hour" in hint.lower()):
        base = tr(lang, "session")
    else:
        base = head.strip() or text.strip()
    tag = tag.strip()
    return "%s·%s" % (base, tag) if tag else base


def remaining_text(seconds, lang="ko"):
    seconds = int(seconds)
    if seconds <= 0:
        return tr(lang, "soon")
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if lang == "en":
        if days:
            return "in %dd %dh" % (days, hours) if hours else "in %dd" % days
        if hours:
            return "in %dh %dm" % (hours, minutes) if minutes else "in %dh" % hours
        return "in %dm" % max(minutes, 1)
    if days:
        return "%d일 %d시간 후" % (days, hours) if hours else "%d일 후" % days
    if hours:
        return "%d시간 %d분 후" % (hours, minutes) if minutes else "%d시간 후" % hours
    return "%d분 후" % max(minutes, 1)


_GENERIC = re.compile(r"^\s*((사용\s*)?한도|usage\s*limit|limit)?\s*$", re.IGNORECASE)
_KO_REL = re.compile(r"((?:\d+\s*(?:일|시간|분)\s*)+)후")
_KO_CLOCK = re.compile(r"(\(([월화수목금토일])(?:요일)?\)\s*)?(오전|오후)\s*(\d{1,2}:\d{2})")
_KO_DATE = re.compile(
    r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?\s*(오전|오후)?\s*(\d{1,2}):(\d{2})")


def short_reset(sub, lang="ko", now=None):
    """Compact reset text for the badge's bottom line.

    Accepts the readers' sub-lines: '2시간 12분 후 재설정', '(월) 오전 8:00에 재설정',
    the Codex page's '2026. 9. 19. 오후 5:10 초기화' (turned into time left), and the
    local reader's two-line 'Recorded …\\n<status>' form (last line wins).
    """
    lines = [line.strip() for line in str(sub or "").splitlines() if line.strip()]
    if not lines:
        return ""
    line = lines[-1]
    if "오래된" in line or "stale" in line.lower():
        return tr(lang, "stale")
    match = _KO_DATE.search(line)
    if match:
        year, month, day, meridiem, hour, minute = match.groups()
        hour = int(hour)
        if meridiem == "오후" and hour < 12:
            hour += 12
        elif meridiem == "오전" and hour == 12:
            hour = 0
        try:
            target = datetime(int(year), int(month), int(day), hour, int(minute))
        except ValueError:
            target = None
        if target is not None:
            now = now or datetime.now()
            return remaining_text((target - now).total_seconds(), lang)
    # Pick out just the time part; page lines can carry extra words around it.
    match = _KO_REL.search(line)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip() + " 후"
    match = _KO_CLOCK.search(line)
    if match:
        day = "(%s) " % match.group(2) if match.group(2) else ""
        return "%s%s %s" % (day, match.group(3), match.group(4))
    line = re.sub(r"\s*(에\s*)?(재설정|초기화)\s*$", "", line)
    line = re.sub(r"^resets?\s+(in\s+)?", "", line, flags=re.IGNORECASE)
    return line.strip()[:18]


def columns(data, lang="ko", now=None):
    """Turn a reader cache into at most two badge columns."""
    if not isinstance(data, dict):
        return [{"warn": True, "label": tr(lang, "syncing")}]
    if data.get("code") == "needs_login":
        return [{"warn": True, "label": tr(lang, "login")}]
    bars = data.get("bars") or []
    if data.get("error") or not bars:
        return [{"warn": True, "label": tr(lang, "failed") if data.get("error") else tr(lang, "syncing")}]
    result = []
    for bar in bars[:2]:
        try:
            pct = max(0.0, min(float(bar.get("pct") or 0), 100.0))
        except (TypeError, ValueError):
            pct = 0.0
        result.append({
            "warn": False,
            "label": short_label(bar.get("label"), lang, bar.get("sub")),
            "pct": pct,
            "pct_text": str(bar.get("pct_text") or "%g%%" % pct),
            "reset": short_reset(bar.get("sub"), lang, now),
            "stale": bool(bar.get("stale")),
        })
    return result


_logged = set()


def log_once(message):
    """Append to the widget's error.log, each distinct message only once."""
    if message in _logged:
        return
    _logged.add(message)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with (STATE_DIR / "error.log").open("a", encoding="utf-8") as stream:
            stream.write("[%s] badges: %s\n" % (time.strftime("%H:%M:%S"), message))
    except OSError:
        pass


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Windows plumbing
# --------------------------------------------------------------------------- #

def _win32():
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    dwmapi = ctypes.windll.dwmapi
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [enum_proc, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    dwmapi.DwmGetWindowAttribute.argtypes = [
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    return user32, kernel32, dwmapi, enum_proc, RECT


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class Windows:
    def __init__(self):
        self.user32, self.kernel32, self.dwmapi, self.enum_proc, self.RECT = _win32()

    def image_name(self, pid):
        from ctypes import wintypes
        handle = self.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if self.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
            return ""
        finally:
            self.kernel32.CloseHandle(handle)

    def frame_rect(self, hwnd):
        rect = self.RECT()
        if self.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
            self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect

    def cloaked(self, hwnd):
        from ctypes import wintypes
        value = wintypes.DWORD()
        ok = self.dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(value), ctypes.sizeof(value)) == 0
        return ok and value.value != 0

    def scale(self, hwnd):
        try:
            return (self.user32.GetDpiForWindow(hwnd) or 96) / 96.0
        except Exception:
            return 1.0

    def shown(self, hwnd):
        return (self.user32.IsWindow(hwnd) and self.user32.IsWindowVisible(hwnd)
                and not self.user32.IsIconic(hwnd) and not self.cloaked(hwnd))

    def find_app_window(self, keywords):
        """Largest taskbar-style window whose process image matches keywords."""
        from ctypes import wintypes
        best, best_area = 0, 0

        def visit(hwnd, _lparam):
            nonlocal best, best_area
            user32 = self.user32
            if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # GW_OWNER
                return True
            if user32.GetWindowLongW(hwnd, -20) & 0x00000080:  # WS_EX_TOOLWINDOW
                return True
            if user32.GetWindowTextLengthW(hwnd) <= 0:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if any(word in self.image_name(pid.value) for word in keywords):
                rect = self.frame_rect(hwnd)
                area = (rect.right - rect.left) * (rect.bottom - rect.top)
                if area > best_area:
                    best, best_area = hwnd, area
            return True

        self.user32.EnumWindows(self.enum_proc(visit), 0)
        return best

    def own(self, badge_hwnd, owner_hwnd):
        # Owned windows stay just above their owner, are covered with it and
        # hide when it is minimized.
        self.user32.SetWindowLongPtrW(badge_hwnd, -8, owner_hwnd)  # GWLP_HWNDPARENT

    def process_alive(self, pid):
        handle = self.kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        try:
            return self.kernel32.WaitForSingleObject(handle, 0) == 0x102  # WAIT_TIMEOUT
        finally:
            self.kernel32.CloseHandle(handle)


# --------------------------------------------------------------------------- #
# Badge UI
# --------------------------------------------------------------------------- #

class Badge:
    def __init__(self, app, key, keywords, cache_name):
        import tkinter as tk

        self.app, self.key, self.keywords = app, key, keywords
        self.cache = STATE_DIR / cache_name
        self.target = 0
        self.drag = None
        self.signature = None
        self.size = (0, 0)
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.withdraw()
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.app.open_widget())
        self.canvas.bind("<Button-3>", self.on_menu)

    def badge_hwnd(self):
        return self.app.win.user32.GetAncestor(self.win.winfo_id(), 2) or self.win.winfo_id()

    # -- drawing -------------------------------------------------------------
    def font(self, size, weight="normal"):
        return ("Segoe UI", -max(8, int(round(size * self.s))), weight)

    def draw(self, cols):
        from tkinter import font as tkfont

        s = self.s
        canvas = self.canvas
        canvas.delete("all")
        label_font, pct_font, small_font = self.font(10.5, "bold"), self.font(10.5, "bold"), self.font(9)
        big = tkfont.Font(root=self.app.root, font=label_font)
        small = tkfont.Font(root=self.app.root, font=small_font)
        measure_label, measure_small = big.measure, small.measure
        # Rows are stacked from the fonts' real line heights so nothing is clipped.
        pad_y = int(PAD_Y * s)
        bar_h = max(2, int(3 * s))
        gap = max(1, int(2 * s))
        y_label = pad_y
        bar_top = y_label + big.metrics("linespace") + gap // 2
        y_reset = bar_top + bar_h + gap
        has_reset = any(not col["warn"] and col["reset"] for col in cols)
        content_bottom = y_reset + small.metrics("linespace") if has_reset else bar_top + bar_h

        widths = []
        for col in cols:
            if col["warn"]:
                widths.append(measure_label("⚠ " + col["label"]))
            else:
                top = measure_label(col["label"]) + int(8 * s) + measure_label(col["pct_text"])
                widths.append(max(top, measure_small(col["reset"]), int(MIN_COL * s)))
        width = int(PAD_X * s) * 2 + sum(widths) + int(COL_GAP * s) * (len(cols) - 1)
        height = content_bottom + pad_y
        canvas.config(width=width, height=height)
        rounded(canvas, 0, 0, width - 1, height - 1, int(8 * s), fill=BG, outline=BORDER)

        x = int(PAD_X * s)
        for col, col_width in zip(cols, widths):
            if col["warn"]:
                canvas.create_text(x, height // 2, text="⚠ " + col["label"], anchor="w",
                                   fill=WARN, font=label_font)
                x += col_width + int(COL_GAP * s)
                continue
            color = level_color(col["pct"], col["stale"])
            y1 = y_label
            canvas.create_text(x, y1, text=col["label"], anchor="nw", fill=DIM, font=label_font)
            canvas.create_text(x + col_width, y1, text=col["pct_text"], anchor="ne",
                               fill=color, font=pct_font)
            bar_bottom = bar_top + bar_h
            canvas.create_rectangle(x, bar_top, x + col_width, bar_bottom, fill=TRACK, outline="")
            fill_to = x + int(col_width * col["pct"] / 100.0)
            if fill_to > x:
                canvas.create_rectangle(x, bar_top, fill_to, bar_bottom, fill=color, outline="")
            if col["reset"]:
                canvas.create_text(x, y_reset, text=col["reset"], anchor="nw",
                                   fill=FAINT, font=small_font)
            x += col_width + int(COL_GAP * s)
        self.size = (width, height)

    def refresh(self, lang):
        cols = columns(read_json(self.cache), lang)
        signature = (json.dumps(cols, sort_keys=True), lang, getattr(self, "s", 1.0))
        if signature != self.signature:
            self.signature = signature
            self.draw(cols)

    # -- placement -----------------------------------------------------------
    def tick(self, lang):
        win = self.app.win
        if not self.target or not win.user32.IsWindow(self.target):
            self.target = win.find_app_window(self.keywords)
            if self.target:
                self.win.geometry("+-20000+-20000")  # map off-screen first: no flash
                self.win.deiconify()
                self.win.update_idletasks()
                win.own(self.badge_hwnd(), self.target)
        if not self.target or not win.shown(self.target):
            if self.win.state() != "withdrawn":
                self.win.withdraw()
            return
        new_scale = win.scale(self.target)
        if getattr(self, "s", None) != new_scale:
            self.s = new_scale
            self.signature = None
        self.refresh(lang)
        if self.win.state() == "withdrawn":
            self.win.deiconify()
        if self.drag:
            return
        rect = win.frame_rect(self.target)
        width, height = self.size
        offset = self.app.positions.get(self.key)
        if offset:
            x = rect.right - int(offset[0] * self.s)
            y = rect.top + int(offset[1] * self.s)
        else:
            x = rect.right - int(BUTTONS * self.s) - width
            y = rect.top + max(0, (int(TITLE_BAR * self.s) - height) // 2)
        self.win.geometry("+%d+%d" % (x, y))

    # -- interaction -----------------------------------------------------------
    def on_press(self, event):
        self.drag = (event.x_root - self.win.winfo_x(), event.y_root - self.win.winfo_y())
        self.press_at = (event.x_root, event.y_root)

    def on_motion(self, event):
        if self.drag:
            self.win.geometry("+%d+%d" % (event.x_root - self.drag[0], event.y_root - self.drag[1]))

    def on_release(self, event):
        start = getattr(self, "press_at", (event.x_root, event.y_root))
        moved = abs(event.x_root - start[0]) + abs(event.y_root - start[1]) > 3
        if self.drag and self.target and moved:
            rect = self.app.win.frame_rect(self.target)
            self.app.positions[self.key] = (
                round((rect.right - self.win.winfo_x()) / self.s),
                round((self.win.winfo_y() - rect.top) / self.s),
            )
            self.app.save_positions()
        self.drag = None

    def on_menu(self, event):
        import tkinter as tk

        menu = tk.Menu(self.win, tearoff=0)
        menu.add_command(label=tr(self.app.lang, "open_widget"), command=self.app.open_widget)
        menu.add_command(label=tr(self.app.lang, "reset_pos"), command=self.reset_position)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def reset_position(self):
        self.app.positions.pop(self.key, None)
        self.app.save_positions()


def rounded(canvas, x1, y1, x2, y2, radius, **options):
    points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
              x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
              x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
    return canvas.create_polygon(points, smooth=True, **options)


class BadgeApp:
    def __init__(self, parent_pid):
        import tkinter as tk

        self.parent_pid = parent_pid
        self.win = Windows()
        self.root = tk.Tk()
        self.root.withdraw()
        self.lang = "ko"
        self.positions = self.load_positions()
        self.badges = [Badge(self, key, words, cache) for key, words, cache in APPS]
        self.last_check = 0.0

    def load_positions(self):
        data = read_json(POSITIONS_FILE) or {}
        clean = {}
        for key, value in data.items():
            if (isinstance(value, list) and len(value) == 2
                    and all(type(v) is int for v in value)):
                clean[key] = tuple(value)
        return clean

    def save_positions(self):
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            POSITIONS_FILE.write_text(json.dumps(self.positions), encoding="utf-8")
        except OSError:
            pass

    def open_widget(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(b"show", ("127.0.0.1", MAIN_PORT))
        except OSError:
            pass

    def housekeeping(self):
        """Every few seconds: follow the widget's language/setting, quit with it."""
        settings = read_json(SETTINGS_FILE) or {}
        self.lang = settings.get("lang") if settings.get("lang") in ("ko", "en") else "ko"
        if settings.get("display") == "widget":
            return False
        if self.parent_pid and not self.win.process_alive(self.parent_pid):
            return False
        return True

    def loop(self):
        now = time.monotonic()
        if now - self.last_check >= 2.0:
            self.last_check = now
            if not self.housekeeping():
                self.root.destroy()
                return
        for badge in self.badges:
            try:
                badge.tick(self.lang)
            except Exception as error:
                log_once("%s: %r" % (badge.key, error))
        self.root.after(120, self.loop)

    def run(self):
        self.loop()
        self.root.mainloop()


def acquire_lock():
    """One helper at a time. A restarting widget may briefly overlap the old
    helper, which exits within ~2 s once its parent is gone, so wait for it."""
    for _ in range(20):
        lock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            lock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            lock.bind(("127.0.0.1", BADGE_PORT))
            return lock
        except OSError:
            lock.close()
            time.sleep(0.5)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=int, default=0)
    args = parser.parse_args()
    if os.name != "nt":
        print("title_badges.py runs on Windows only.")
        return 1
    enable_dpi_awareness()
    lock = acquire_lock()
    if lock is None:
        return 0
    try:
        BadgeApp(args.parent).run()
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
