"""Read exact Claude plan usage from the official Settings > Usage page.

Claude does not publish a subscription-usage API. ClaudePet therefore opens
the real Usage page in a dedicated Chrome/Edge profile and reads the two meters
that Anthropic renders there. The browser owns the login session; this script
never reads cookies, tokens, or credential files.

Commands:
    usage.py --sync       Refresh the official page and write latest.json.
    usage.py --connect    Open the dedicated browser for first-time login.
    usage.py --close      Stop a background browser started by Claude Usage.
    usage.py --self-test  Test the browser protocol and DOM parser offline.
"""

import argparse
import base64
import ctypes
import hashlib
import json
import os
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


DIR = os.path.dirname(os.path.abspath(__file__))
LATEST = os.path.join(DIR, "latest.json")
USAGE_URL = "https://claude.ai/settings/usage"

# UI language for the labels and status text this script emits ("ko" or "en"),
# set from --lang. Claude's own reset text is scraped from the page and follows
# the account's language.
LANG = "ko"

LOCAL_DATA = os.environ.get("LOCALAPPDATA") or os.path.join(
    os.path.expanduser("~"), "AppData", "Local"
)
APP_DATA = os.path.join(LOCAL_DATA, "ClaudePet")
PROFILE = os.path.join(APP_DATA, "BrowserProfile")
STATE = os.path.join(APP_DATA, "browser_state.json")
READY = os.path.join(APP_DATA, "connected.json")

CONNECT_TIMEOUT = 12
PAGE_TIMEOUT = 20


class SyncError(Exception):
    """A recoverable sync failure suitable for the widget."""


class NeedsLogin(SyncError):
    """The dedicated browser profile is not signed in to Claude."""


class HiddenDesktopProcess:
    """Small Popen-like wrapper for a process on a non-interactive desktop."""

    def __init__(self, process_handle, pid, desktop_handle):
        self._process_handle = process_handle
        self._desktop_handle = desktop_handle
        self.pid = int(pid)

    def poll(self):
        exit_code = ctypes.c_ulong()
        if not ctypes.windll.kernel32.GetExitCodeProcess(
            self._process_handle, ctypes.byref(exit_code)
        ):
            return 1
        return None if exit_code.value == 259 else int(exit_code.value)

    def terminate(self):
        ctypes.windll.kernel32.TerminateProcess(self._process_handle, 1)

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        milliseconds = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000))
        result = ctypes.windll.kernel32.WaitForSingleObject(
            self._process_handle, milliseconds
        )
        if result == 0x102:
            raise subprocess.TimeoutExpired("hidden browser", timeout)
        code = self.poll()
        return 0 if code is None else code

    def close_handles(self):
        if self._process_handle:
            ctypes.windll.kernel32.CloseHandle(self._process_handle)
            self._process_handle = None
        if self._desktop_handle:
            ctypes.windll.user32.CloseDesktop(self._desktop_handle)
            self._desktop_handle = None

    def __del__(self):
        try:
            self.close_handles()
        except (AttributeError, OSError):
            pass


def launch_on_hidden_desktop(arguments):
    """Launch a normal browser on a separate Windows desktop with no UI surface."""
    from ctypes import wintypes

    class StartupInfo(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("lpReserved", wintypes.LPWSTR),
            ("lpDesktop", wintypes.LPWSTR),
            ("lpTitle", wintypes.LPWSTR),
            ("dwX", wintypes.DWORD),
            ("dwY", wintypes.DWORD),
            ("dwXSize", wintypes.DWORD),
            ("dwYSize", wintypes.DWORD),
            ("dwXCountChars", wintypes.DWORD),
            ("dwYCountChars", wintypes.DWORD),
            ("dwFillAttribute", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("wShowWindow", wintypes.WORD),
            ("cbReserved2", wintypes.WORD),
            ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
            ("hStdInput", wintypes.HANDLE),
            ("hStdOutput", wintypes.HANDLE),
            ("hStdError", wintypes.HANDLE),
        ]

    class ProcessInfo(ctypes.Structure):
        _fields_ = [
            ("hProcess", wintypes.HANDLE),
            ("hThread", wintypes.HANDLE),
            ("dwProcessId", wintypes.DWORD),
            ("dwThreadId", wintypes.DWORD),
        ]

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.CreateDesktopW.restype = wintypes.HANDLE
    desktop_name = "ClaudeUsageHidden"
    desktop = user32.CreateDesktopW(
        desktop_name, None, None, 0, 0x10000000, None  # GENERIC_ALL
    )
    if not desktop:
        raise ctypes.WinError()

    startup = StartupInfo()
    startup.cb = ctypes.sizeof(startup)
    startup.lpDesktop = desktop_name
    startup.dwFlags = 1  # STARTF_USESHOWWINDOW
    startup.wShowWindow = 0  # SW_HIDE
    process_info = ProcessInfo()
    command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments))
    created = kernel32.CreateProcessW(
        arguments[0],
        command,
        None,
        None,
        False,
        getattr(subprocess, "CREATE_NO_WINDOW", 0),
        None,
        None,
        ctypes.byref(startup),
        ctypes.byref(process_info),
    )
    if not created:
        error = ctypes.WinError()
        user32.CloseDesktop(desktop)
        raise error
    kernel32.CloseHandle(process_info.hThread)
    return HiddenDesktopProcess(
        process_info.hProcess, process_info.dwProcessId, desktop
    )


def atomic_json(path, payload):
    """Write JSON without exposing the widget to a half-written file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    os.replace(temp, path)


def emit(payload, write_latest=True):
    if write_latest:
        atomic_json(LATEST, payload)
    # stdout may be CP949 on Korean Windows. The widget reads latest.json, so
    # keep stdout ASCII-safe instead of risking a UnicodeEncodeError.
    print(json.dumps(payload, ensure_ascii=True))


def browser_candidates():
    roots = [
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        LOCAL_DATA,
    ]
    relative = [
        os.path.join("Google", "Chrome", "Application", "chrome.exe"),
        os.path.join("Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for name in ("chrome.exe", "msedge.exe", "chrome", "microsoft-edge"):
        found = shutil.which(name)
        if found:
            yield found
    for root in roots:
        if not root:
            continue
        for item in relative:
            yield os.path.join(root, item)


def find_browser():
    seen = set()
    for path in browser_candidates():
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(path):
            return path
    raise SyncError("Chrome 또는 Edge를 찾지 못했습니다")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def load_state():
    try:
        with open(STATE, encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def save_state(data):
    atomic_json(STATE, data)


def http_json(url, method="GET", timeout=2):
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def debug_alive(port):
    try:
        http_json("http://127.0.0.1:%d/json/version" % int(port), timeout=1)
        return True
    except (OSError, ValueError, urllib.error.URLError):
        return False


def stop_owned_browser(state):
    """Stop only a hidden browser process that this app recorded itself."""
    if state.get("mode") != "background":
        return
    try:
        pid = int(state.get("pid", 0))
    except (TypeError, ValueError):
        return
    if pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def hide_browser_windows(pid):
    """Hide top-level windows owned by the dedicated browser on Windows."""
    if os.name != "nt" or not pid:
        return
    try:
        user32 = ctypes.windll.user32
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p
        )

        @callback_type
        def hide_if_owned(window, _state):
            owner = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(window, ctypes.byref(owner))
            if owner.value == int(pid):
                user32.ShowWindow(window, 0)  # SW_HIDE
            return True

        user32.EnumWindows(hide_if_owned, 0)
    except (AttributeError, OSError, ValueError):
        pass


def hidden_startupinfo():
    """Ask Windows not to show the browser's first GUI window."""
    if os.name != "nt":
        return None
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return startup


def wait_for_debug(port, process=None, hidden_pid=None):
    deadline = time.time() + CONNECT_TIMEOUT
    while time.time() < deadline:
        if hidden_pid:
            hide_browser_windows(hidden_pid)
        if debug_alive(port):
            if hidden_pid:
                hide_browser_windows(hidden_pid)
            return
        if process is not None and process.poll() is not None:
            break
        time.sleep(0.2)
    raise SyncError("사용량 브라우저를 시작하지 못했습니다")


def browser_flags(port, profile, visible):
    flags = [
        "--remote-debugging-port=%d" % port,
        # Only our local DevTools client (Origin: http://localhost) may attach;
        # blocks a malicious web page from reaching the debug port (e.g. via DNS
        # rebinding). The port itself is bound to loopback.
        "--remote-allow-origins=http://localhost",
        "--user-data-dir=%s" % profile,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-mode",
    ]
    if visible:
        flags.extend(["--new-window", USAGE_URL])
    else:
        # Keep a normal (non-headless) browser for Claude's anti-bot checks, but
        # place it off-screen as a second guard while Win32 keeps it hidden.
        flags.extend(
            [
                "--start-minimized",
                "--window-position=-32000,-32000",
                "--window-size=1,1",
                "about:blank",
            ]
        )
    return flags


def launch_browser(visible):
    os.makedirs(APP_DATA, exist_ok=True)
    os.makedirs(PROFILE, exist_ok=True)
    browser = find_browser()
    port = free_port()
    creationflags = 0
    if not visible and os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    arguments = [browser] + browser_flags(port, PROFILE, visible)
    if not visible and os.name == "nt":
        process = launch_on_hidden_desktop(arguments)
    else:
        process = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            startupinfo=hidden_startupinfo() if not visible else None,
        )
    state = {
        "pid": process.pid,
        "port": port,
        "mode": "visible" if visible else "background",
        "browser": browser,
        "profile": PROFILE,
    }
    save_state(state)
    if not visible:
        hide_browser_windows(process.pid)
    wait_for_debug(port, process, hidden_pid=process.pid if not visible else None)
    return state


def ensure_browser():
    state = load_state()
    if state.get("port") and debug_alive(state["port"]):
        if state.get("mode") == "background":
            hide_browser_windows(state.get("pid"))
        return state
    if not os.path.isfile(READY):
        raise NeedsLogin("Claude 로그인이 필요합니다")
    return launch_browser(visible=False)


def connect_browser():
    state = load_state()
    if state.get("port") and debug_alive(state["port"]):
        if state.get("mode") == "visible":
            open_page(state["port"], USAGE_URL)
            return state
        stop_owned_browser(state)
        time.sleep(0.8)
    return launch_browser(visible=True)


def open_page(port, url):
    encoded = urllib.parse.quote(url, safe="")
    return http_json(
        "http://127.0.0.1:%d/json/new?%s" % (int(port), encoded),
        method="PUT",
        timeout=3,
    )


def page_target(port):
    targets = http_json("http://127.0.0.1:%d/json/list" % int(port), timeout=3)
    pages = [item for item in targets if item.get("type") == "page"]
    for item in pages:
        if "claude.ai" in item.get("url", ""):
            return item
    if pages:
        return pages[0]
    return open_page(port, "about:blank")


class WebSocket:
    """Tiny RFC 6455 client, sufficient for the local Chrome DevTools socket."""

    def __init__(self, url, timeout=10):
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "ws":
            raise SyncError("지원하지 않는 브라우저 연결 방식입니다")
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout)
        self.socket.settimeout(timeout)
        self.buffer = b""
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            "GET %s HTTP/1.1\r\n"
            "Host: %s:%s\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: http://localhost\r\n\r\n"
        ) % (path, parsed.hostname, parsed.port, key)
        self.socket.sendall(request.encode("ascii"))
        headers = self._read_headers()
        if not headers.startswith(b"HTTP/1.1 101"):
            raise SyncError("브라우저 연결이 거부되었습니다")
        expected = base64.b64encode(
            hashlib.sha1(
                (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")
            ).digest()
        )
        if b"sec-websocket-accept: " + expected.lower() not in headers.lower():
            raise SyncError("브라우저 연결을 확인하지 못했습니다")

    def _read_headers(self):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise SyncError("브라우저 연결이 닫혔습니다")
            data += chunk
            if len(data) > 65536:
                raise SyncError("브라우저 응답이 너무 큽니다")
        headers, self.buffer = data.split(b"\r\n\r\n", 1)
        return headers

    def _read_exact(self, size):
        while len(self.buffer) < size:
            chunk = self.socket.recv(max(4096, size - len(self.buffer)))
            if not chunk:
                raise SyncError("브라우저 연결이 닫혔습니다")
            self.buffer += chunk
        result, self.buffer = self.buffer[:size], self.buffer[size:]
        return result

    def send_frame(self, opcode, payload=b""):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self.socket.sendall(bytes(header) + masked)

    def recv_message(self):
        chunks = []
        message_opcode = None
        while True:
            first, second = self._read_exact(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(length)
            if mask:
                payload = bytes(
                    byte ^ mask[index % 4] for index, byte in enumerate(payload)
                )
            if opcode == 0x8:
                raise SyncError("브라우저 연결이 종료되었습니다")
            if opcode == 0x9:
                self.send_frame(0xA, payload)
                continue
            if opcode in (0x1, 0x2):
                message_opcode = opcode
                chunks = [payload]
            elif opcode == 0x0 and message_opcode is not None:
                chunks.append(payload)
            else:
                continue
            if final:
                return b"".join(chunks).decode("utf-8", errors="replace")

    def send_json(self, payload):
        self.send_frame(0x1, json.dumps(payload, separators=(",", ":")))

    def recv_json(self):
        return json.loads(self.recv_message())

    def close(self):
        try:
            self.send_frame(0x8)
        except OSError:
            pass
        try:
            self.socket.close()
        except OSError:
            pass


class DevTools:
    def __init__(self, websocket_url):
        self.websocket = WebSocket(websocket_url)
        self.request_id = 0

    def call(self, method, params=None):
        self.request_id += 1
        request_id = self.request_id
        self.websocket.send_json(
            {"id": request_id, "method": method, "params": params or {}}
        )
        while True:
            message = self.websocket.recv_json()
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise SyncError(message["error"].get("message", "브라우저 명령 실패"))
            return message.get("result", {})

    def evaluate(self, expression):
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        remote = result.get("result", {})
        if remote.get("subtype") == "error":
            raise SyncError(remote.get("description", "페이지 읽기 실패"))
        return remote.get("value")

    def close(self):
        self.websocket.close()


METER_EXPRESSION = r"""
(() => {
  const RESET = /재설정|초기화|resets?\s+(in|at|on)/i;
  const text = node => ((node && node.innerText) || '').trim();
  const split = node => text(node).split(/\n+/)
    .map(value => value.trim()).filter(Boolean);

  // Walk outwards from the label instead of assuming a fixed nesting depth,
  // so an extra wrapper around the meter row does not hide the reset text.
  const findReset = (labelElement, label) => {
    let node = labelElement;
    for (let depth = 0; node && depth < 6; depth += 1) {
      node = node.parentElement;
      if (!node) break;
      const hit = split(node).find(value => value !== label && RESET.test(value));
      if (hit) return hit;
    }
    const legacy = labelElement?.parentElement?.parentElement;
    return split(legacy).filter(value => value !== label).join(' ');
  };

  // aria-valuenow is the documented source; fall back to the rendered text.
  const percent = meter => {
    // A missing attribute reads back as null, and Number(null) is 0, so an
    // absent aria-valuenow would otherwise be reported as a real 0%.
    const raw = meter.getAttribute('aria-valuenow');
    const now = raw === null || raw.trim() === '' ? NaN : Number(raw);
    if (Number.isFinite(now)) return now;
    const source = meter.getAttribute('aria-valuetext') || text(meter);
    const match = source.match(/(\d+(?:\.\d+)?)\s*%/);
    return match ? Number(match[1]) : null;
  };

  const meters = Array.from(document.querySelectorAll('[role="meter"]'));
  return {
    url: location.href,
    title: document.title,
    body: (document.body?.innerText || '').slice(0, 2500),
    meters: meters.map(meter => {
      const id = meter.getAttribute('aria-labelledby');
      const labelElement = id ? document.getElementById(id) : null;
      const label = labelElement
        ? text(labelElement)
        : (meter.getAttribute('aria-label') || '').trim();
      return {
        label,
        reset: findReset(labelElement || meter, label),
        pct: percent(meter),
        pctText: meter.getAttribute('aria-valuetext') || ''
      };
    })
  };
})()
"""


def read_page(devtools):
    return devtools.evaluate(METER_EXPRESSION) or {}


def wait_for_usage(devtools):
    deadline = time.time() + PAGE_TIMEOUT
    last = {}
    while time.time() < deadline:
        last = read_page(devtools)
        if len(last.get("meters") or []) >= 2:
            return last
        body = (last.get("body") or "").lower()
        url = (last.get("url") or "").lower()
        if (
            "/login" in url
            or "google로 계속하기" in body
            or "이메일로 계속하기" in body
            or "continue with google" in body
            or "continue with email" in body
            or "보안 확인 수행 중" in body
            or "security verification" in body
            or "cloudflare" in body
        ):
            raise NeedsLogin("Claude 로그인이 필요합니다")
        time.sleep(0.5)
    if len(last.get("meters") or []) < 2:
        raise SyncError("공식 사용량을 읽지 못했습니다")
    return last


def refresh_usage(devtools, navigate=True):
    devtools.call("Page.enable")
    if navigate:
        devtools.call("Page.navigate", {"url": USAGE_URL})
    data = wait_for_usage(devtools)
    clicked = devtools.evaluate(
        r"""
(() => {
  const button = Array.from(document.querySelectorAll('button')).find(item =>
    /새로고침|refresh/i.test((item.innerText || item.getAttribute('aria-label') || '').trim())
  );
  if (!button) return false;
  button.click();
  return true;
})()
"""
    )
    if clicked:
        time.sleep(1.2)
        data = wait_for_usage(devtools)
    return data


SESSION_LABELS = ("current session", "현재 세션")
ALL_MODEL_LABELS = ("all models", "모든 모델")


def clean_label(label, index):
    en = LANG == "en"
    session = "Current session" if en else "현재 세션"
    all_models = "All models" if en else "모든 모델"
    lowered = (label or "").strip().lower()
    if any(pattern in lowered for pattern in SESSION_LABELS):
        return session
    if any(pattern in lowered for pattern in ALL_MODEL_LABELS):
        return all_models
    return session if index == 0 else all_models


def find_meter(meters, patterns):
    for meter in meters:
        label = (meter.get("label") or "").strip().lower()
        if any(pattern in label for pattern in patterns):
            return meter
    return None


def pick_meters(meters):
    """Select the two meters by label so extra or reordered ones do not shift."""
    usable = [
        meter
        for meter in meters
        if isinstance(meter.get("pct"), (int, float))
        and not isinstance(meter.get("pct"), bool)
    ]
    session = find_meter(usable, SESSION_LABELS)
    all_models = find_meter(usable, ALL_MODEL_LABELS)
    rest = [
        meter for meter in usable if meter is not session and meter is not all_models
    ]
    if session is None and rest:
        session = rest.pop(0)
    if all_models is None and rest:
        all_models = rest.pop(0)
    return [meter for meter in (session, all_models) if meter is not None]


def make_payload(data):
    selected = pick_meters(data.get("meters") or [])
    if len(selected) < 2:
        raise SyncError("공식 사용량 막대를 찾지 못했습니다")
    bars = []
    for index, meter in enumerate(selected):
        pct = meter.get("pct")
        if not isinstance(pct, (int, float)):
            raise SyncError("공식 사용량 값이 올바르지 않습니다")
        rounded = round(max(0, min(float(pct), 100)), 1)
        bars.append(
            {
                "label": clean_label(meter.get("label"), index),
                "pct": rounded,
                "pct_text": "%g%%" % rounded,
                "sub": (meter.get("reset") or "").strip(),
            }
        )
    return {
        "source": "official",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "bars": bars,
    }


def sync_usage():
    state = ensure_browser()
    target = page_target(state["port"])
    websocket_url = target.get("webSocketDebuggerUrl")
    if not websocket_url:
        raise SyncError("사용량 페이지에 연결하지 못했습니다")
    devtools = DevTools(websocket_url)
    try:
        payload = make_payload(refresh_usage(devtools))
        atomic_json(READY, {"connected_at": payload["synced_at"]})
        return payload
    finally:
        devtools.close()


def close_browser():
    stop_owned_browser(load_state())


def self_test():
    """Exercise Chrome startup, WebSocket framing, and meter parsing offline."""
    global LANG
    LANG = "ko"  # assertions below pin the Korean labels
    browser = find_browser()
    # Chrome can still hold profile files for a moment after it exits.
    with tempfile.TemporaryDirectory(
        prefix="claudepet-test-", ignore_cleanup_errors=True
    ) as profile:
        port = free_port()
        arguments = [browser] + browser_flags(port, profile, visible=False)
        if os.name == "nt":
            process = launch_on_hidden_desktop(arguments)
        else:
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        try:
            hide_browser_windows(process.pid)
            wait_for_debug(port, process, hidden_pid=process.pid)
            target = page_target(port)
            devtools = DevTools(target["webSocketDebuggerUrl"])
            try:
                # The fixture deliberately mimics the ways the real page can
                # drift: an unrelated meter listed first, an extra wrapper
                # around the label, and a meter without aria-valuenow.
                fixture = """
<!doctype html><html><body>
<div><div><div><span id="opus">Opus limit</span></div></div><span>Resets in 5 hours</span></div>
<div role="meter" aria-labelledby="opus" aria-valuenow="12" aria-valuetext="12% used"></div>
<div><div><div><span id="current">Current session</span></div></div><span>Resets in 2 hours</span></div>
<div role="meter" aria-labelledby="current" aria-valuemin="0" aria-valuemax="100"
     aria-valuenow="100" aria-valuetext="100% used"></div>
<div><div><span id="weekly">All models</span></div><span>Resets in 19 hours</span></div>
<div role="meter" aria-labelledby="weekly" aria-valuemin="0" aria-valuemax="100"
     aria-valuetext="69% used"></div>
</body></html>
"""
                url = "data:text/html," + urllib.parse.quote(fixture)
                devtools.call("Page.navigate", {"url": url})
                deadline = time.time() + 5
                data = {}
                while time.time() < deadline:
                    data = read_page(devtools)
                    if len(data.get("meters") or []) >= 3:
                        break
                    time.sleep(0.1)
                payload = make_payload(data)
                assert payload["bars"][0]["label"] == "현재 세션"
                assert payload["bars"][1]["label"] == "모든 모델"
                assert payload["bars"][0]["pct"] == 100
                assert payload["bars"][1]["pct"] == 69
                assert payload["bars"][0]["sub"] == "Resets in 2 hours"
                assert payload["bars"][1]["sub"] == "Resets in 19 hours"
            finally:
                devtools.close()
        finally:
            try:
                process.terminate()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
    print("Claude Usage browser sync self-test: OK")


def main():
    global LANG
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true")
    group.add_argument("--connect", action="store_true")
    group.add_argument("--close", action="store_true")
    group.add_argument("--self-test", action="store_true")
    parser.add_argument("--lang", choices=("ko", "en"), default="ko")
    args = parser.parse_args()
    LANG = args.lang
    en = LANG == "en"

    if args.connect:
        connect_browser()
        emit(
            {"message": "Sign in to Claude, then press the refresh button again"
             if en else "Claude 로그인 후 펫의 새로고침 버튼을 다시 누르세요"},
            write_latest=False,
        )
        return
    if args.close:
        close_browser()
        return
    if args.self_test:
        self_test()
        return

    try:
        emit(sync_usage())
    except NeedsLogin:
        try:
            os.remove(READY)
        except OSError:
            pass
        emit(
            {
                "code": "needs_login",
                "error": "Official usage needs sign-in\nPress ↻ to sign in to Claude"
                if en else "공식 사용량 연결 필요\n↻를 눌러 Claude에 로그인하세요",
            }
        )
    except (OSError, ValueError, SyncError) as error:
        emit(
            {
                "code": "sync_failed",
                "error": "Official usage sync failed" if en else "공식 사용량 동기화 실패",
                "detail": str(error),
            }
        )
    # The hidden background browser is deliberately left running between syncs:
    # it holds the signed-in session in memory (Claude rotates its auth token, so
    # killing the browser after every sync would drop the login and force a fresh
    # sign-in each time). The loopback debug port is already protected by
    # --remote-allow-origins=http://localhost, and the browser is stopped on exit
    # via `usage.py --close`.


if __name__ == "__main__":
    main()
