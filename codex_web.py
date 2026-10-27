"""Read Codex/Work usage from the official ChatGPT usage page.

The local reader (codex_usage.py) only sees usage that goes through the Codex
CLI; usage from the ChatGPT app/web is not written to ~/.codex. This reader
opens the real usage page in a dedicated browser profile and reads the numbers
ChatGPT renders there, so app/web usage is included -- the same idea as the
Claude reader (usage.py), whose browser plumbing this module reuses.

The browser owns the login session; this script never reads cookies, tokens, or
credential files. It only reads the rendered page.

Commands:
    codex_web.py --sync       Refresh the usage page and write codex_latest.json.
    codex_web.py --connect    Open the dedicated browser for first-time login.
    codex_web.py --close      Stop the background browser started for Codex.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import usage  # reuse the browser/CDP plumbing

# The official Codex/Work usage analytics page (confirmed via probe).
CODEX_USAGE_URL = "https://chatgpt.com/codex/cloud/settings/analytics#usage"
# Runtime cache under LOCALAPPDATA (shared with the widget), not the program
# folder, so it works even in a read-only or OneDrive-synced install location.
CODEX_LATEST = os.path.join(usage.CACHE_DIR, "codex_latest.json")

# Isolate the ChatGPT login/profile from Claude's dedicated browser.
usage.USAGE_URL = CODEX_USAGE_URL
usage.PROFILE = os.path.join(usage.APP_DATA, "CodexBrowserProfile")
usage.STATE = os.path.join(usage.APP_DATA, "codex_browser_state.json")
usage.READY = os.path.join(usage.APP_DATA, "codex_connected.json")

LANG = "ko"
PAGE_TIMEOUT = 20

SyncError = usage.SyncError
NeedsLogin = usage.NeedsLogin


def codex_target(port):
    targets = usage.http_json("http://127.0.0.1:%d/json/list" % int(port), timeout=3)
    pages = [item for item in targets if item.get("type") == "page"]
    for item in pages:
        url = item.get("url", "")
        if "chatgpt.com" in url or "openai.com" in url:
            return item
    if pages:
        return pages[0]
    return usage.open_page(port, CODEX_USAGE_URL)


# The usage page has no ARIA meters; values are plain spans. Collect the
# smallest DOM blocks that carry a percent, a reset marker and a limit label,
# and return their text lines. The fragile line parsing is done in Python
# (parse_block) so it can be unit-tested offline.
EXTRACT_JS = r"""
(() => {
  const RESET = /초기화|resets?/i;
  const LIMIT = /한도|limit/i;
  const PCT = /\d+(?:\.\d+)?\s*%/;
  const text = n => ((n && n.innerText) || '').trim();
  const qualifies = t => !!t && t.length <= 240 && PCT.test(t) && RESET.test(t) && LIMIT.test(t);

  const blocks = [];
  const seen = new Set();
  for (const el of Array.from(document.querySelectorAll('body *'))) {
    const t = text(el);
    if (!qualifies(t)) continue;
    let childQualifies = false;
    for (const c of el.children) { if (qualifies(text(c))) { childQualifies = true; break; } }
    if (childQualifies) continue;
    if (seen.has(t)) continue;
    seen.add(t);
    blocks.push(t.split(/\n+/).map(s => s.trim()).filter(Boolean));
  }
  return {
    url: location.href,
    title: document.title,
    body: (document.body ? document.body.innerText : '').slice(0, 1500),
    blocks: blocks
  };
})()
"""

import re

_PCT_ONLY = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")
_PCT_ANY = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_LIMIT = re.compile(r"한도|limit", re.IGNORECASE)
_RESET = re.compile(r"초기화|resets?", re.IGNORECASE)
_REMAIN = re.compile(r"남음|remaining|left", re.IGNORECASE)
_USED = re.compile(r"사용됨|used", re.IGNORECASE)
_SHARE = re.compile(r"공유|share|동일", re.IGNORECASE)
_LABEL_PREFIX = re.compile(r"^(.{0,20}?(?:한도|limit))\s*(?=\d)", re.IGNORECASE)
_GENERIC_LABEL = re.compile(r"^\s*((사용\s*)?한도|(usage\s*)?limit)\s*$", re.IGNORECASE)
# Everything after the reset word is page noise run into the same line
# ("…후 초기화됩니다37% 남음"); keep the line up to "초기화"/"재설정".
_RESET_WORD = re.compile(r"초기화|재설정")
_TRAILING_PCT = re.compile(r"\s*\d+(?:\.\d+)?\s*%.*$")


def parse_block(lines):
    """Turn one block's text lines into {label, used, reset} or None.

    The page reports "남음"/remaining; we convert to a used percent so the
    widget shows usage consistently (bar fills as you consume quota).
    """
    lines = [line.strip() for line in lines if line and line.strip()]
    if not lines:
        return None

    # A real usage-limit card always shows a reset time; require it so unrelated
    # blocks (e.g. "Skills used 100%") are not mistaken for a limit.
    reset = next((line for line in lines if _RESET.search(line)), "")
    if not reset:
        return None

    # Label: shortest limit line that is a heading, not the shared-limit note.
    label_candidates = [
        line for line in lines
        if _LIMIT.search(line) and not _SHARE.search(line) and len(line) <= 24
    ]
    label = min(label_candidates, key=len) if label_candidates else ""

    # The page can render the limit name and the reset time as one run of text
    # ("주간 사용 한도6일 16시간 후 초기화됩니다"). Split the name off; it is the
    # more specific label when the heading is just "사용 한도".
    match = _LABEL_PREFIX.match(reset)
    if match:
        prefix = match.group(1).strip()
        reset = reset[match.end():].strip()
        if not label or _GENERIC_LABEL.match(label):
            label = prefix
    match = _RESET_WORD.search(reset)
    if match:
        reset = reset[:match.end()]
    reset = _TRAILING_PCT.sub("", reset).strip()

    # Percent + remaining/used: prefer a standalone "35%" line and read the
    # neighbouring word; otherwise fall back to the first percent in the block.
    pct = None
    remaining = None
    for index, line in enumerate(lines):
        match = _PCT_ONLY.match(line)
        if not match:
            continue
        pct = float(match.group(1))
        neighbour = " ".join(lines[index:index + 2])
        if _REMAIN.search(neighbour) and not _USED.search(neighbour):
            remaining = True
        elif _USED.search(neighbour):
            remaining = False
        break
    if pct is None:
        joined = " ".join(lines)
        match = _PCT_ANY.search(joined)
        if not match:
            return None
        pct = float(match.group(1))
        remaining = bool(_REMAIN.search(joined)) and not _USED.search(joined)
    if remaining is None:
        remaining = bool(_REMAIN.search(" ".join(lines)))

    pct = max(0.0, min(pct, 100.0))
    used = round(100.0 - pct if remaining else pct, 1)
    return {"label": label or ("사용 한도" if LANG != "en" else "Usage limit"),
            "used": used, "reset": reset}


_KO_LABEL_WORDS = (
    (r"주간", "Weekly"), (r"일일", "Daily"), (r"월간", "Monthly"),
    (r"(\d+)\s*시간", r"\1-hour"), (r"(\d+)\s*일", r"\1-day"),
    (r"(사용\s*)?한도", "limit"),
)


def normalize_label(label):
    """Compact the page label for the narrow widget, in the widget's language.

    The page follows the ChatGPT account language, so a Korean page shown in an
    English widget gets its words translated ("주간 사용 한도" -> "Weekly limit").
    """
    label = (label or "").strip()
    if not label:
        return label
    if LANG == "en" and re.search("[가-힣]", label):
        for pattern, word in _KO_LABEL_WORDS:
            label = re.sub(pattern, word, label)
        label = re.sub(r"\s+", " ", label).strip()
        if label.lower() == "limit":
            return "Usage limit"
        return label[:1].upper() + label[1:]
    if LANG != "en" and not re.search("[가-힣]", label):
        low = label.lower()
        if "week" in low:
            return "주간 한도"
        match = re.search(r"(\d+)[\s-]*hour", low)
        if match:
            return "%s시간 한도" % match.group(1)
        if re.fullmatch(r"(usage\s*)?limits?", low):
            return "사용 한도"
    # "주간 사용 한도" -> "주간 한도"; keep others as-is.
    return label.replace("사용 한도", "한도").strip()


def make_payload(data):
    en = LANG == "en"
    blocks = data.get("blocks") or []
    bars = []
    for block in blocks:
        parsed = parse_block(block)
        if parsed is None:
            continue
        sub = usage.localize_reset(parsed["reset"], LANG) or ("from ChatGPT" if en else "ChatGPT 공식 페이지")
        bars.append({
            "label": normalize_label(parsed["label"]),
            "pct": parsed["used"],
            "pct_text": "%g%%" % parsed["used"],
            "sub": sub,
            "stale": False,
        })
    if not bars:
        raise SyncError(
            "No Codex usage found on the page" if en
            else "사용 한도를 페이지에서 찾지 못했습니다"
        )
    return {
        "source": "codex-web",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "limit_id": "codex-web",
        "bars": bars,
    }


def read_page(devtools):
    return devtools.evaluate(EXTRACT_JS) or {}


def wait_for_usage(devtools):
    deadline = time.time() + PAGE_TIMEOUT
    last = {}
    while time.time() < deadline:
        last = read_page(devtools)
        if last.get("blocks"):
            return last
        body = (last.get("body") or "").lower()
        url = (last.get("url") or "").lower()
        if ("/auth" in url or "/login" in url or "login.openai" in url
                or "log in" in body or "sign in" in body or "로그인" in body
                or "continue with" in body or "이메일로 계속" in body):
            raise NeedsLogin(usage.t("ChatGPT 로그인이 필요합니다", "ChatGPT sign-in is needed"))
        time.sleep(0.5)
    if not last.get("blocks"):
        raise SyncError(usage.t("사용 한도를 읽지 못했습니다", "Could not read the usage limits"))
    return last


def refresh_usage(devtools):
    devtools.call("Page.enable")
    current = read_page(devtools)
    if not current.get("blocks"):
        devtools.call("Page.navigate", {"url": CODEX_USAGE_URL})
    return wait_for_usage(devtools)


def sync_usage():
    last_error = None
    for _attempt in range(2):
        state = usage.ensure_browser()
        target = codex_target(state["port"])
        websocket_url = target.get("webSocketDebuggerUrl")
        if not websocket_url:
            raise SyncError(usage.t("사용량 페이지에 연결하지 못했습니다", "Could not connect to the usage page"))
        devtools = usage.DevTools(websocket_url, state["port"])
        try:
            payload = make_payload(refresh_usage(devtools))
            usage.atomic_json(usage.READY, {"connected_at": payload["synced_at"]})
            return payload
        except NeedsLogin:
            raise
        except (usage.socket.timeout, SyncError, OSError) as error:
            last_error = error
        finally:
            devtools.close()
        time.sleep(1.0)
    raise last_error


def connect_browser():
    state = usage.connect_browser()
    usage.atomic_json(usage.READY, {"connected_at": datetime.now(timezone.utc).isoformat()})
    return state


def emit(payload):
    usage.atomic_json(CODEX_LATEST, payload)
    import json
    print(json.dumps(payload, ensure_ascii=True))


def main():
    global LANG
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true")
    group.add_argument("--connect", action="store_true")
    group.add_argument("--close", action="store_true")
    parser.add_argument("--lang", choices=("ko", "en"), default="ko")
    args = parser.parse_args()
    LANG = args.lang
    usage.LANG = LANG  # shared browser helpers word their errors in this language

    if args.close:
        usage.close_browser()
        return
    if args.connect:
        connect_browser()
        return

    en = LANG == "en"
    try:
        emit(sync_usage())
    except NeedsLogin:
        try:
            os.remove(usage.READY)
        except OSError:
            pass
        emit_error(
            "needs_login",
            "Codex usage needs ChatGPT sign-in\nPress ↻ to sign in"
            if en else "Codex 사용량 연결 필요\n↻를 눌러 ChatGPT에 로그인하세요",
        )
    except SyncError as error:
        emit_error("sync_failed", str(error))
    except (OSError, ValueError) as error:
        emit_error("sync_failed",
                   "Failed to read Codex usage" if en else "Codex 사용량 읽기 실패",
                   str(error))


def emit_error(code, message, detail=None):
    """Write the error to the shared cache (so the widget sees it) and echo it."""
    import json
    payload = {"code": code, "error": message}
    if detail:
        payload["detail"] = detail
    try:
        usage.atomic_json(CODEX_LATEST, payload)
    except OSError:
        pass
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
