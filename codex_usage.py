"""Read exact Codex (ChatGPT plan) usage from local Codex CLI session logs.

Codex does not publish a subscription-usage API, and the CLI only shows a
partial number in its status line. It does, however, record the server-supplied
rate-limit snapshot in every session rollout file. This script reads the most
recent snapshot straight from disk and writes it in the same ``bars`` shape that
``usage.py`` produces for Claude, so the same widget can render either source.

Unlike the Claude reader, this never launches a browser and never needs a login:
the Codex CLI already wrote the numbers locally while you used it. That also makes
it cross-platform (Windows, Linux, macOS, Raspberry Pi).

Where the data comes from
    ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
Each rollout is JSON-lines. A ``token_count`` event carries::

    {"type": "event_msg", "payload": {"type": "token_count",
      "rate_limits": {"primary":   {"used_percent": 12.3, "window_minutes": 300,
                                     "resets_at": 1779571027},
                      "secondary": {"used_percent": 27.0, "window_minutes": 10080,
                                    "resets_at": 1779999999},
                      "plan_type": "pro"}}}

``primary`` is the short rolling window (about 5 hours); ``secondary`` is the
weekly window. Older CLI builds and idle sessions write ``rate_limits: null``,
so we scan recent files and keep the newest event that actually has a snapshot.

Commands:
    codex_usage.py --sync       Read the newest snapshot and write codex_latest.json.
    codex_usage.py --self-test  Parse a synthetic fixture offline (no ~/.codex needed).
"""

import argparse
import glob
import json
import math
import os
import tempfile
from datetime import datetime, timezone


DIR = os.path.dirname(os.path.abspath(__file__))
LATEST = os.path.join(DIR, "codex_latest.json")

# UI language for the labels and reset text this script emits ("ko" or "en").
# Set from --lang; the widget passes its own language through.
LANG = "ko"

# How far back to look, and how many recent files to inspect. A single active
# session's last token_count is normally the global newest, but concurrent
# sessions mean we compare timestamps across a handful of recent files.
SCAN_DAYS = 14
SCAN_FILES = 24

# Skip pathologically long lines before parsing them as JSON. A real
# token_count line is a few hundred bytes; this only guards against a corrupt
# or hostile rollout with a huge blob exhausting memory on json.loads.
MAX_LINE_CHARS = 2_000_000
# A local snapshot cannot confirm usage after this much inactivity.
STALE_SECONDS = 300


class SyncError(Exception):
    """A recoverable read failure suitable for the widget."""


def codex_home():
    """Return the Codex data directory, honouring CODEX_HOME like the CLI does."""
    override = os.environ.get("CODEX_HOME")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(os.path.expanduser("~"), ".codex")


def sessions_dir(home=None):
    return os.path.join(home or codex_home(), "sessions")


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
    # stdout may be CP949 on Korean Windows; the widget reads codex_latest.json,
    # so keep stdout ASCII-safe instead of risking a UnicodeEncodeError.
    print(json.dumps(payload, ensure_ascii=True))


def recent_rollouts(home=None):
    """Yield rollout file paths, newest modification time first."""
    root = sessions_dir(home)
    if not os.path.isdir(root):
        return []
    matches = glob.glob(os.path.join(root, "**", "rollout-*.jsonl"), recursive=True)
    if not matches:
        return []
    cutoff = None
    if SCAN_DAYS:
        cutoff = datetime.now(timezone.utc).timestamp() - SCAN_DAYS * 86400

    def mtime(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    dated = sorted(((mtime(path), path) for path in matches), reverse=True)
    if cutoff is not None:
        fresh = [item for item in dated if item[0] >= cutoff]
        # Never end up with nothing just because clocks or copies look old.
        dated = fresh or dated[:1]
    return [path for _mtime, path in dated[:SCAN_FILES]]


def parse_time(value):
    """Best-effort parse of an ISO-8601 or epoch timestamp into epoch seconds."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    except ValueError:
        try:
            number = datetime.fromisoformat(value.strip().replace("Z", "+00:00")).timestamp()
        except (ValueError, OSError, OverflowError):
            return None
    try:
        datetime.fromtimestamp(number, timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
    return number


def find_token_count(obj):
    """Read actual events, not similarly-shaped data inside tool output."""
    if not isinstance(obj, dict):
        return None
    node = obj.get("payload") if obj.get("type") == "event_msg" else obj
    if isinstance(node, dict) and node.get("type") == "token_count":
        return node
    return None


def finite_number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def bounded_lines(handle):
    """Discard oversized lines in bounded chunks, including their entire tail."""
    while True:
        line = handle.readline(MAX_LINE_CHARS + 1)
        if not line:
            return
        if len(line) > MAX_LINE_CHARS:
            while line and not line.endswith("\n"):
                line = handle.readline(MAX_LINE_CHARS + 1)
            continue
        yield line


def newest_snapshot(home=None):
    """Scan recent rollout files and return (rate_limits, event_epoch).

    Selects the general Codex bucket; unidentified legacy snapshots also qualify.
    """
    best = None  # (event_epoch, rate_limits)
    for path in recent_rollouts(home):
        try:
            file_epoch = os.path.getmtime(path)
        except OSError:
            file_epoch = 0.0
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in bounded_lines(handle):
                    line = line.strip()
                    if not line or '"token_count"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except (ValueError, RecursionError):
                        continue
                    payload = find_token_count(obj)
                    if not payload:
                        continue
                    limits = payload.get("rate_limits")
                    if not isinstance(limits, dict):
                        continue
                    if limits.get("limit_id") not in (None, "", "codex"):
                        continue
                    if not any(
                        isinstance(limits.get(key), dict)
                        and finite_number(limits[key].get("used_percent"))
                        for key in ("primary", "secondary")
                    ):
                        continue
                    when = (
                        parse_time(obj.get("timestamp"))
                        or parse_time(payload.get("timestamp"))
                        or file_epoch
                    )
                    if best is None or when >= best[0]:
                        best = (when, limits)
        except OSError:
            continue
    if best is None:
        return None, None
    return best[1], best[0]


def window_label(minutes):
    """Name a rate-limit window from its server-supplied duration in minutes."""
    en = LANG == "en"
    try:
        minutes = int(round(float(minutes)))
    except (TypeError, ValueError, OverflowError):
        return "Usage" if en else "사용량"
    table = {
        300: ("Current session", "현재 세션"),   # ~5 hours, short rolling window
        10080: ("Weekly limit", "주간 한도"),     # 7 days
        1440: ("Daily limit", "일일 한도"),       # 24 hours
        43200: ("Monthly limit", "월간 한도"),    # 30 days
        525600: ("Yearly limit", "연간 한도"),    # 365 days
    }
    if minutes in table:
        return table[minutes][0 if en else 1]
    if minutes % 10080 == 0:
        weeks = minutes // 10080
        return "%d-week limit" % weeks if en else "%d주 한도" % weeks
    if minutes % 1440 == 0:
        days = minutes // 1440
        return "%d-day limit" % days if en else "%d일 한도" % days
    if minutes % 60 == 0:
        hours = minutes // 60
        return "%d-hour limit" % hours if en else "%d시간 한도" % hours
    return "%d-min limit" % minutes if en else "%d분 한도" % minutes


def reset_at_epoch(window, event_epoch):
    """Resolve a window's reset moment to epoch seconds.

    Newer builds send an absolute ``resets_at``; older ones send a relative
    ``resets_in_seconds`` measured from the event that carried it.
    """
    absolute = window.get("resets_at")
    if finite_number(absolute) and absolute > 0:
        return parse_time(absolute)
    relative = window.get("resets_in_seconds")
    if finite_number(relative) and relative >= 0 and event_epoch:
        return parse_time(float(event_epoch) + float(relative))
    return None


def human_reset(reset_epoch, now_epoch=None):
    """Render a 'resets in ...' string like the Claude widget shows."""
    en = LANG == "en"
    if not reset_epoch:
        return ""
    now = now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp()
    delta = int(reset_epoch - now)
    if delta <= 0:
        return "resets soon" if en else "곧 재설정"
    days, remainder = divmod(delta, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
    if en:
        if days >= 1:
            return "resets in %dd %dh" % (days, hours) if hours else "resets in %dd" % days
        if hours >= 1:
            return "resets in %dh %dm" % (hours, minutes) if minutes else "resets in %dh" % hours
        if minutes >= 1:
            return "resets in %dm" % minutes
        return "resets soon"
    if days >= 1:
        return "%d일 %d시간 후 재설정" % (days, hours) if hours else "%d일 후 재설정" % days
    if hours >= 1:
        return "%d시간 %d분 후 재설정" % (hours, minutes) if minutes else "%d시간 후 재설정" % hours
    if minutes >= 1:
        return "%d분 후 재설정" % minutes
    return "곧 재설정"


def make_bar(window, event_epoch, now_epoch=None):
    if not isinstance(window, dict):
        return None
    pct = window.get("used_percent")
    if not finite_number(pct):
        return None
    rounded = round(max(0.0, min(float(pct), 100.0)), 1)
    now = now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp()
    reset = reset_at_epoch(window, event_epoch)
    observed = parse_time(event_epoch)
    stale = (observed is None or abs(now - observed) > STALE_SECONDS
             or (reset is not None and reset <= now))
    recorded = (datetime.fromtimestamp(observed, timezone.utc).astimezone().strftime("%m/%d %H:%M")
                if observed is not None else "?")
    if stale:
        status = "Stale · refresh in Codex" if LANG == "en" else "오래된 기록 · Codex에서 갱신"
    else:
        status = human_reset(reset, now)
    return {
        "label": window_label(window.get("window_minutes")),
        "pct": rounded,
        "pct_text": ("%g%%" % rounded) + ("*" if stale else ""),
        "sub": ("Recorded " if LANG == "en" else "기록 ") + recorded + "\n" + status,
        "stale": stale,
    }


def make_payload(limits, event_epoch, now_epoch=None):
    en = LANG == "en"
    if not isinstance(limits, dict):
        raise SyncError(
            "No Codex usage data found" if en else "Codex 사용량 데이터를 찾지 못했습니다"
        )
    bars = []
    for key in ("primary", "secondary"):
        bar = make_bar(limits.get(key), event_epoch, now_epoch)
        if bar:
            bars.append(bar)
    if not bars:
        raise SyncError(
            "No Codex usage bars found" if en else "Codex 사용량 막대를 찾지 못했습니다"
        )
    payload = {
        "source": "codex-local",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "observed_at": datetime.fromtimestamp(event_epoch, timezone.utc).isoformat(),
        "limit_id": "codex",
        "bars": bars,
    }
    plan = limits.get("plan_type")
    if isinstance(plan, str) and plan:
        payload["plan_type"] = plan
    return payload


def sync_usage(home=None):
    en = LANG == "en"
    limits, event_epoch = newest_snapshot(home)
    if limits is None:
        root = sessions_dir(home)
        if not os.path.isdir(root):
            raise SyncError(
                "Codex session folder not found\nRun the Codex CLI once"
                if en else
                "Codex 세션 폴더를 찾지 못했습니다\nCodex CLI를 한 번 실행하세요"
            )
        raise SyncError(
            "No general Codex usage recorded\nSend one prompt with Codex"
            if en else
            "Codex 기본 한도 기록이 없습니다\nCodex로 프롬프트를 한 번 보내세요"
        )
    return make_payload(limits, event_epoch)


FIXTURE_LINES = [
    # An early session line with no rate-limit snapshot yet.
    {"timestamp": "2026-08-30T10:00:00Z", "type": "event_msg",
     "payload": {"type": "token_count", "rate_limits": None,
                 "total_token_usage": {"total_tokens": 10}}},
    # A newer file might briefly write null again; we must not pick this over a
    # real snapshot that is older in wall-clock terms.
    {"timestamp": "2026-08-31T09:00:00Z", "type": "event_msg",
     "payload": {"type": "token_count", "rate_limits": None}},
    # The real, newest snapshot.
    {"timestamp": "2026-08-31T12:34:00Z", "type": "event_msg",
     "payload": {"type": "token_count",
                 "rate_limits": {
                     "limit_id": "codex",
                     "primary": {"used_percent": 100.0, "window_minutes": 300,
                                 "resets_at": 1000000000 + 2 * 3600},
                     "secondary": {"used_percent": 69.0, "window_minutes": 10080,
                                   "resets_at": 1000000000 + 19 * 3600},
                     "plan_type": "pro"}}},
]


def self_test():
    """Parse a synthetic rollout offline: no ~/.codex and no network needed."""
    global LANG
    LANG = "ko"  # assertions below pin the Korean strings
    with tempfile.TemporaryDirectory(prefix="codexusage-test-") as home:
        day = os.path.join(sessions_dir(home), "2026", "08", "31")
        os.makedirs(day, exist_ok=True)
        with open(os.path.join(day, "rollout-2026-08-31T12-30-00-abc.jsonl"),
                  "w", encoding="utf-8") as handle:
            for line in FIXTURE_LINES:
                handle.write(json.dumps(line) + "\n")

        limits, event_epoch = newest_snapshot(home)
        assert limits is not None, "snapshot not found"
        assert limits["plan_type"] == "pro"
        # Pin 'now' so the reset text is deterministic regardless of today.
        now = event_epoch
        limits["primary"]["resets_at"] = now + 2 * 3600
        limits["secondary"]["resets_at"] = now + 19 * 3600
        payload = make_payload(limits, event_epoch, now_epoch=now)
        assert payload["bars"][0]["label"] == "현재 세션", payload["bars"][0]
        assert payload["bars"][1]["label"] == "주간 한도", payload["bars"][1]
        assert payload["bars"][0]["pct"] == 100.0
        assert payload["bars"][1]["pct"] == 69.0
        assert payload["bars"][0]["sub"].endswith("2시간 후 재설정"), payload["bars"][0]["sub"]
        assert payload["bars"][1]["sub"].endswith("19시간 후 재설정"), payload["bars"][1]["sub"]
        assert payload["plan_type"] == "pro"

        # Window-label fallbacks for durations without a friendly name.
        assert window_label(1440) == "일일 한도"
        assert window_label(180) == "3시간 한도"
        assert window_label(90) == "90분 한도"
        # Relative reset (older schema) resolves against the event time.
        rel = make_bar({"used_percent": 5, "window_minutes": 300,
                        "resets_in_seconds": 3600}, now, now_epoch=now)
        assert rel["sub"].endswith("1시간 후 재설정"), rel["sub"]
    print("Codex local usage self-test: OK")


def main():
    global LANG
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true")
    group.add_argument("--self-test", action="store_true")
    parser.add_argument("--lang", choices=("ko", "en"), default="ko")
    args = parser.parse_args()
    LANG = args.lang

    if args.self_test:
        self_test()
        return

    try:
        emit(sync_usage())
    except SyncError as error:
        emit({"code": "sync_failed", "error": str(error)})
    except (OSError, ValueError) as error:
        emit(
            {
                "code": "sync_failed",
                "error": "Failed to read Codex usage" if LANG == "en"
                else "Codex 사용량 읽기 실패",
                "detail": str(error),
            }
        )


if __name__ == "__main__":
    main()
