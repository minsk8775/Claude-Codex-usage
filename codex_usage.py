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
import os
import tempfile
from datetime import datetime, timezone


DIR = os.path.dirname(os.path.abspath(__file__))
LATEST = os.path.join(DIR, "codex_latest.json")

# How far back to look, and how many recent files to inspect. A single active
# session's last token_count is normally the global newest, but concurrent
# sessions mean we compare timestamps across a handful of recent files.
SCAN_DAYS = 14
SCAN_FILES = 24


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
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def find_token_count(obj):
    """Return the token_count payload inside a rollout line, or None.

    Rollout schemas have shifted over releases (a raw payload, an ``event_msg``
    wrapper, deeper nesting), so walk the structure instead of hard-coding a
    single path.
    """
    stack = [obj]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("type") == "token_count" and "rate_limits" in node:
                return node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return None


def newest_snapshot(home=None):
    """Scan recent rollout files and return (rate_limits, event_epoch).

    Keeps the event with the greatest timestamp whose rate_limits is not null.
    """
    best = None  # (event_epoch, rate_limits)
    for path in recent_rollouts(home):
        try:
            file_epoch = os.path.getmtime(path)
        except OSError:
            file_epoch = 0.0
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or '"token_count"' not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    payload = find_token_count(obj)
                    if not payload:
                        continue
                    limits = payload.get("rate_limits")
                    if not isinstance(limits, dict):
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
    try:
        minutes = int(round(float(minutes)))
    except (TypeError, ValueError):
        return "사용량"
    table = {
        300: "현재 세션",     # ~5 hours, the short rolling window
        10080: "주간 한도",   # 7 days
        1440: "일일 한도",    # 24 hours
        43200: "월간 한도",   # 30 days
        525600: "연간 한도",  # 365 days
    }
    if minutes in table:
        return table[minutes]
    if minutes % 10080 == 0:
        return "%d주 한도" % (minutes // 10080)
    if minutes % 1440 == 0:
        return "%d일 한도" % (minutes // 1440)
    if minutes % 60 == 0:
        return "%d시간 한도" % (minutes // 60)
    return "%d분 한도" % minutes


def reset_at_epoch(window, event_epoch):
    """Resolve a window's reset moment to epoch seconds.

    Newer builds send an absolute ``resets_at``; older ones send a relative
    ``resets_in_seconds`` measured from the event that carried it.
    """
    absolute = window.get("resets_at")
    if isinstance(absolute, (int, float)) and absolute > 0:
        return float(absolute)
    relative = window.get("resets_in_seconds")
    if isinstance(relative, (int, float)) and relative >= 0 and event_epoch:
        return float(event_epoch) + float(relative)
    return None


def human_reset(reset_epoch, now_epoch=None):
    """Render a Korean 'resets in ...' string like the Claude widget shows."""
    if not reset_epoch:
        return ""
    now = now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp()
    delta = int(reset_epoch - now)
    if delta <= 0:
        return "곧 재설정"
    days, remainder = divmod(delta, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes = remainder // 60
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
    if not isinstance(pct, (int, float)) or isinstance(pct, bool):
        return None
    rounded = round(max(0.0, min(float(pct), 100.0)), 1)
    return {
        "label": window_label(window.get("window_minutes")),
        "pct": rounded,
        "pct_text": "%g%%" % rounded,
        "sub": human_reset(reset_at_epoch(window, event_epoch), now_epoch),
    }


def make_payload(limits, event_epoch, now_epoch=None):
    if not isinstance(limits, dict):
        raise SyncError("Codex 사용량 데이터를 찾지 못했습니다")
    bars = []
    for key in ("primary", "secondary"):
        bar = make_bar(limits.get(key), event_epoch, now_epoch)
        if bar:
            bars.append(bar)
    if not bars:
        raise SyncError("Codex 사용량 막대를 찾지 못했습니다")
    payload = {
        "source": "codex-local",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "bars": bars,
    }
    plan = limits.get("plan_type")
    if isinstance(plan, str) and plan:
        payload["plan_type"] = plan
    return payload


def sync_usage(home=None):
    limits, event_epoch = newest_snapshot(home)
    if limits is None:
        root = sessions_dir(home)
        if not os.path.isdir(root):
            raise SyncError(
                "Codex 세션 폴더를 찾지 못했습니다\nCodex CLI를 한 번 실행하세요"
            )
        raise SyncError(
            "Codex 사용량 기록이 없습니다\nCodex로 프롬프트를 한 번 보내세요"
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
        now = 1000000000.0
        payload = make_payload(limits, event_epoch, now_epoch=now)
        assert payload["bars"][0]["label"] == "현재 세션", payload["bars"][0]
        assert payload["bars"][1]["label"] == "주간 한도", payload["bars"][1]
        assert payload["bars"][0]["pct"] == 100.0
        assert payload["bars"][1]["pct"] == 69.0
        assert payload["bars"][0]["sub"] == "2시간 후 재설정", payload["bars"][0]["sub"]
        assert payload["bars"][1]["sub"] == "19시간 후 재설정", payload["bars"][1]["sub"]
        assert payload["plan_type"] == "pro"

        # Window-label fallbacks for durations without a friendly name.
        assert window_label(1440) == "일일 한도"
        assert window_label(180) == "3시간 한도"
        assert window_label(90) == "90분 한도"
        # Relative reset (older schema) resolves against the event time.
        rel = make_bar({"used_percent": 5, "window_minutes": 300,
                        "resets_in_seconds": 3600}, now, now_epoch=now)
        assert rel["sub"] == "1시간 후 재설정", rel["sub"]
    print("Codex local usage self-test: OK")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sync", action="store_true")
    group.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

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
                "error": "Codex 사용량 읽기 실패",
                "detail": str(error),
            }
        )


if __name__ == "__main__":
    main()
