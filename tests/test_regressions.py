"""Offline regression tests: no real profiles, usage logs or installed widget."""
import importlib.machinery
import importlib.util
import io
import json
import os
import queue
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


REPO = Path(__file__).resolve().parents[1]


def load(name, filename):
    loader = importlib.machinery.SourceFileLoader(name, str(REPO / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


codex = load("tested_codex", "codex_usage.py")
claude = load("tested_claude", "usage.py")
widget = load("tested_widget", "claude_usage.pyw") if os.name == "nt" else None


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / "sessions").mkdir()
        self.rollout = self.home / "sessions" / "rollout-test.jsonl"
        self.now = datetime.now(timezone.utc).timestamp()
        codex.LANG = "en"

    def event(self, percent=85, limit_id="codex", age=1, reset_in=3600):
        return {
            "timestamp": self.now - age,
            "type": "event_msg",
            "payload": {"type": "token_count", "rate_limits": {
                "limit_id": limit_id,
                "primary": {"used_percent": percent, "window_minutes": 300,
                            "resets_at": self.now + reset_in},
            }},
        }

    def write(self, *rows):
        self.rollout.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_model_bucket_cannot_replace_codex(self):
        self.write(self.event(age=2), self.event(2, "codex_bengalfox"))
        payload = codex.sync_usage(str(self.home))
        self.assertEqual(payload["bars"][0]["pct"], 85)
        self.assertEqual(payload["limit_id"], "codex")

    def test_model_only_is_not_presented_as_general_usage(self):
        self.write(self.event(2, "codex_bengalfox"))
        with self.assertRaises(codex.SyncError):
            codex.sync_usage(str(self.home))

    def test_legacy_unidentified_snapshot_is_supported(self):
        row = self.event()
        del row["payload"]["rate_limits"]["limit_id"]
        self.write(row)
        self.assertEqual(codex.sync_usage(str(self.home))["bars"][0]["pct"], 85)

    def test_expired_snapshot_keeps_observation_time_and_warns(self):
        self.write(self.event(100, age=86400, reset_in=-3600))
        payload = codex.sync_usage(str(self.home))
        self.assertEqual(datetime.fromisoformat(payload["observed_at"]).timestamp(), self.now - 86400)
        self.assertTrue(payload["bars"][0]["stale"])
        self.assertIn("stale", payload["bars"][0]["sub"].lower())
        self.assertNotEqual(payload["bars"][0]["pct_text"], "100%")

    def test_old_unexpired_snapshot_is_also_marked_stale(self):
        self.write(self.event(age=86400, reset_in=3600))
        self.assertTrue(codex.sync_usage(str(self.home))["bars"][0]["stale"])

    def test_non_finite_numbers_and_nested_fake_events_are_ignored(self):
        fake = {"type": "response_item", "timestamp": self.now,
                "payload": {"tool_result": self.event(1, age=0)["payload"]}}
        self.write(self.event(age=5), self.event(float("nan"), age=2),
                   self.event(float("inf"), age=1), fake)
        self.assertEqual(codex.sync_usage(str(self.home))["bars"][0]["pct"], 85)

    def test_malformed_shapes_and_deep_json_do_not_hide_valid_snapshot(self):
        self.write(self.event(age=5), [self.event(1)], self.event(age=0))
        with self.rollout.open("a", encoding="utf-8") as stream:
            stream.write('[' * 2000 + '"token_count"' + ']' * 2000 + '\n')
        self.assertEqual(codex.sync_usage(str(self.home))["bars"][0]["pct"], 85)

    def test_oversized_line_is_discarded_without_unbounded_reads(self):
        self.write(self.event())
        text = 'x' * 5000 + '\n' + self.rollout.read_text(encoding="utf-8")
        class BoundedReader(io.StringIO):
            def readline(self, size=-1):
                if size < 0 or size > 1025:
                    raise AssertionError("unbounded log read")
                return super().readline(size)
            def __iter__(self):
                raise AssertionError("unbounded log iteration")
        with patch.object(codex, "MAX_LINE_CHARS", 1024), patch("builtins.open", return_value=BoundedReader(text)):
            self.assertEqual(codex.newest_snapshot(str(self.home))[0]["primary"]["used_percent"], 85)

    def test_invalid_numeric_timestamps_do_not_crash(self):
        for value in (True, float("nan"), float("inf"), "1e999", 1e100, 10**400):
            with self.subTest(value=value):
                self.assertIsNone(codex.parse_time(value))

    def test_huge_integers_do_not_hide_valid_usage(self):
        self.write(self.event(age=2), self.event(10**400))
        self.assertEqual(codex.sync_usage(str(self.home))["bars"][0]["pct"], 85)


class BrowserTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Win32 process handles")
    def test_reused_pid_or_wrong_executable_is_not_terminated(self):
        path = os.path.normcase(os.path.abspath("browser.exe"))
        state = {"mode": "background", "pid": 42, "process_created": 100,
                 "browser": path, "profile": claude.PROFILE}
        for identity in ((path, 101), (path + ".other", 100)):
            api = Mock()
            api.OpenProcess.return_value = 1234
            with self.subTest(identity=identity), patch.object(claude, "windows_process_api", return_value=api), patch.object(claude, "process_identity", return_value=identity):
                self.assertFalse(claude.stop_owned_browser(state))
            api.TerminateProcess.assert_not_called()
            api.CloseHandle.assert_called_once_with(1234)

    @unittest.skipUnless(os.name == "nt", "Win32 process handles")
    def test_verified_browser_uses_same_open_handle_for_termination(self):
        path = os.path.normcase(os.path.abspath("browser.exe"))
        state = {"mode": "background", "pid": 42, "process_created": 100,
                 "browser": path, "profile": claude.PROFILE}
        api = Mock()
        api.OpenProcess.return_value = 1234
        api.WaitForSingleObject.return_value = 0
        with patch.object(claude, "windows_process_api", return_value=api), patch.object(claude, "process_identity", return_value=(path, 100)) as identity:
            self.assertTrue(claude.stop_owned_browser(state))
        identity.assert_called_once_with(api, 1234)
        api.TerminateProcess.assert_called_once_with(1234, 0)
        api.CloseHandle.assert_called_once_with(1234)

    def test_old_state_never_kills_a_pid_without_identity(self):
        with patch.object(claude.os, "kill") as kill:
            claude.stop_owned_browser({"mode": "background", "pid": 424242})
        kill.assert_not_called()

    def test_websocket_rejects_remote_endpoints_before_connecting(self):
        for url in ("ws://example.com:9222/devtools/page/1", "ws://127.0.0.1:9222@evil.test/x"):
            with self.subTest(url=url), patch.object(claude.socket, "create_connection", side_effect=claude.SyncError("unexpected connect")) as connect:
                with self.assertRaises(claude.SyncError):
                    claude.WebSocket(url)
                connect.assert_not_called()

    def test_oversized_websocket_message_is_rejected_before_payload_read(self):
        ws = claude.WebSocket.__new__(claude.WebSocket)
        ws._read_exact = Mock(side_effect=[bytes([0x81, 127]), (2**40).to_bytes(8, "big")])
        with self.assertRaises(claude.SyncError):
            ws.recv_message()
        self.assertEqual(ws._read_exact.call_count, 2)

    def test_fragmented_message_cannot_bypass_size_limit(self):
        ws = claude.WebSocket.__new__(claude.WebSocket)
        ws._read_exact = Mock(side_effect=[bytes([0x01, 4]), b"abcd", bytes([0x80, 4])])
        with patch.object(claude, "MAX_MESSAGE_BYTES", 6), self.assertRaises(claude.SyncError):
            ws.recv_message()
        self.assertEqual(ws._read_exact.call_count, 3)

    def test_http_rejects_remote_urls_and_disables_redirects(self):
        with patch.object(claude.urllib.request, "build_opener") as opener:
            with self.assertRaises(claude.SyncError):
                claude.http_json("http://example.com/debug")
            opener.assert_not_called()
        self.assertIsNone(claude.NoRedirectHandler().redirect_request(None, None, 302, "", {}, "http://example.com"))

    def test_http_response_is_bounded_and_localhost_is_not_resolved(self):
        opener = Mock()
        response = Mock()
        response.read.return_value = b"x" * 9
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch.object(claude, "MAX_MESSAGE_BYTES", 8), patch.object(claude.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(claude.SyncError):
                claude.http_json("http://localhost:1234/json/version")
        response.read.assert_called_once_with(9)
        self.assertEqual(opener.open.call_args.args[0].host, "127.0.0.1:1234")


class Root:
    def __init__(self):
        self.visibility = "normal"
    def state(self):
        return self.visibility
    def withdraw(self):
        self.visibility = "withdrawn"
    def deiconify(self):
        self.visibility = "normal"
    def lift(self):
        pass
    def attributes(self, *args):
        pass
    def after(self, *args):
        pass


@unittest.skipUnless(widget, "Windows widget")
class WidgetTests(unittest.TestCase):
    def app(self):
        app = widget.UsageApp.__new__(widget.UsageApp)
        app.root = Root()
        app.mode = "auto"
        app.auto_view = "claude"
        app._known_app_keys = {"claude"}
        app.exiting = False
        app.on_top = True
        app.page = 0
        app.syncing = False
        app.pending_sync = None
        app.lang = "ko"
        app.datas = {"claude": {}, "codex": {"error": "no cache"}}
        app.data = {}
        app.tray = Mock()
        app.lang_var = Mock()
        app._save_settings = Mock()
        app._draw = Mock()
        app._place = Mock()
        app.events = queue.Queue()
        return app

    def test_hide_survives_ticks_and_reopens_when_app_relaunches(self):
        app = self.app()
        app.hide()
        with patch.object(widget, "running_app_keys", return_value={"claude"}):
            app._auto_tick()
        self.assertEqual(app.root.state(), "withdrawn")
        with patch.object(widget, "running_app_keys", return_value=set()), patch.object(app, "start_sync"):
            app._auto_tick()
        with patch.object(widget, "running_app_keys", return_value={"claude"}), patch.object(app, "start_sync"):
            app._auto_tick()
        self.assertEqual(app.root.state(), "normal")

    def test_mode_and_language_changes_sync_latest_settings_after_completion(self):
        app = self.app()
        app.mode = "claude"
        app.syncing = True
        with patch.object(widget.threading, "Thread") as thread:
            app._set_mode("codex")
            app._set_lang("en")
            thread.assert_not_called()
            app.events.put(("sync_done", None))
            app._poll_events()
            thread.assert_called_once()
            sources, manual, lang = thread.call_args.kwargs["args"]
            self.assertEqual([source["key"] for source in sources], ["codex"])
            self.assertEqual(lang, "en")

    def test_internal_events_cannot_be_injected_over_udp(self):
        app = self.app()
        app.control_socket = Mock()
        app.control_socket.recvfrom.side_effect = [
            (b"sync_result", ("127.0.0.1", 1)),
            (b"sync_done", ("127.0.0.1", 1)),
            (b"sh\xffow", ("127.0.0.1", 1)),
            (b"show", ("127.0.0.1", 1)), OSError("closed")]
        app._listen()
        self.assertEqual(list(app.events.queue), [("show", None)])

    def test_untrusted_origin_subpath_is_rejected(self):
        with patch.object(widget, "run_git", return_value=Mock(returncode=0, stdout=widget.REPO_URL + "/other")), patch.dict(os.environ, {}, clear=True):
            self.assertFalse(widget.update_checks_allowed())

    def test_manual_login_request_is_preserved_while_syncing(self):
        app = self.app()
        app.syncing = True
        app.start_sync(True)
        app.start_sync(False)
        with patch.object(widget.threading, "Thread") as thread:
            app.events.put(("sync_done", None))
            app._poll_events()
            self.assertTrue(thread.call_args.kwargs["args"][1])

    def test_closed_widget_does_not_start_pending_sync(self):
        app = self.app()
        app.exiting = True
        with patch.object(widget.threading, "Thread") as thread:
            app.start_sync(True)
            thread.assert_not_called()

    def test_oversized_udp_datagram_does_not_stop_listener(self):
        app = self.app()
        app.control_socket = Mock()
        oversized = OSError("oversized")
        oversized.winerror = 10040
        app.control_socket.recvfrom.side_effect = [oversized, (b"show", ("127.0.0.1", 1)), OSError("closed")]
        app._listen()
        self.assertEqual(list(app.events.queue), [("show", None)])

    def test_git_failure_is_nonfatal_and_never_runs_checkout(self):
        with patch.object(widget, "run_git", side_effect=FileNotFoundError("git")), patch.object(widget, "log_error"):
            self.assertFalse(widget.updates_available())

    def test_update_checks_only_official_main_and_requires_ahead_commit(self):
        calls = []
        def run(*args):
            calls.append(args)
            output = {("remote", "get-url", "origin"): widget.REPO_URL + ".git",
                      ("rev-parse", "HEAD"): "local",
                      ("rev-parse", "FETCH_HEAD"): "new"}
            return Mock(returncode=0, stdout=output.get(args, "install.py\n"), stderr="")
        with patch.object(widget, "run_git", side_effect=run), patch.dict(os.environ, {}, clear=True):
            self.assertTrue(widget.updates_available())
        self.assertIn(("fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "origin", "main"), calls)
        self.assertFalse(any("@{u}" in args or "checkout" in args or "pull" in args for args in calls))

    def test_reader_failure_does_not_reuse_a_successful_cache(self):
        app = self.app()
        app._load_latest = Mock(return_value={"bars": [{"pct": 1}]})
        with patch.object(widget, "run_script", return_value=Mock(returncode=1, stderr="failed")), patch.object(widget, "log_error"):
            app._sync_worker([widget.SOURCE_BY_KEY["codex"]], False, "en")
        app._load_latest.assert_not_called()
        self.assertIn("error", app.events.get_nowait()[1][1])

    def test_watcher_survives_oversized_packets_and_uses_app_transitions(self):
        control = Mock()
        oversized = OSError("oversized")
        oversized.winerror = 10040
        control.recvfrom.side_effect = [oversized, socket.timeout(), socket.timeout(), (b"exit", ("127.0.0.1", 1))]
        with patch.object(widget, "bind_control", return_value=control), patch.object(widget, "running_app_keys", side_effect=[{"claude"}, {"claude"}, set(), {"claude"}]), patch.object(widget, "AUTO_FILE") as auto, patch.object(widget, "start_main") as start:
            auto.exists.return_value = True
            self.assertEqual(widget.run_watcher(), 0)
        self.assertEqual(start.call_count, 2)
        control.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
