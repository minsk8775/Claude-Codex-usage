"""Offline regression tests: no real profiles, usage logs or installed widget."""
import importlib.machinery
import importlib.util
import os
import queue
import socket
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


REPO = Path(__file__).resolve().parents[1]


def load(name, filename):
    loader = importlib.machinery.SourceFileLoader(name, str(REPO / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


claude = load("tested_claude", "usage.py")
badges = load("tested_badges", "title_badges.py")
sys.path.insert(0, str(REPO))  # codex_web imports usage
web = load("tested_codex_web", "codex_web.py")
widget = load("tested_widget", "claude_usage.pyw") if os.name == "nt" else None


class BadgeTests(unittest.TestCase):
    NOW = datetime(2026, 10, 22, 15, 0)

    def test_reset_text_is_shortened_for_every_reader_format(self):
        cases = {
            "2시간 12분 후 재설정": "2시간 12분 후 초기화",
            "(월) 오전 8:00에 재설정": "(월) 오전 8:00",
            "2026. 10. 24. 오후 5:10 초기화": "2일 2시간 후 초기화",
            "2026. 10. 22. 오전 12:30 초기화": "곧 초기화",
            "기록 10/22 14:58\n3시간 후 재설정": "3시간 후 초기화",
            "(월요일) 오전 8:00에 재설정": "(월) 오전 8:00",
            "주간 사용 한도와 동일 · 1시간 20분 후 초기화": "1시간 20분 후 초기화",
            "주간 사용 한도6일 16시간 후 초기화됩니다": "6일 16시간 후 초기화",
            "": "",
        }
        for sub, expected in cases.items():
            self.assertEqual(badges.short_reset(sub, "ko", self.NOW), expected, sub)
        english = {
            "Resets in 2 hr 12 min": "in 2h 12m",
            "Resets in 6 d 16 hr": "in 6d 16h",
            "Resets Mon 8:00 AM": "Mon 8:00 AM",
            "Resets Oct 24, 5:10 PM": "in 2d 2h",      # same form as a duration
            "Resets Jan 2, 9:00 AM": "in 71d 18h",     # next year's January
        }
        for sub, expected in english.items():
            self.assertEqual(badges.short_reset(sub, "en", self.NOW), expected, sub)

    def test_labels_are_compact_and_keep_model_tags(self):
        self.assertEqual(badges.short_label("현재 세션"), "세션")
        self.assertEqual(badges.short_label("모든 모델"), "주간")
        self.assertEqual(badges.short_label("주간 한도 · Spark"), "주간·Spark")
        self.assertEqual(badges.short_label("Current session", "en"), "Session")
        self.assertEqual(badges.short_label("5시간 한도"), "세션")
        self.assertEqual(badges.short_label("한도", "ko", "주간 사용 한도 초기화"), "주간")
        self.assertEqual(badges.short_label("한도", "ko", "1시간 후 초기화"), "한도")

    def test_columns_cover_login_errors_and_bars(self):
        self.assertEqual(badges.columns({"code": "needs_login", "error": "x"})[0]["label"], "로그인 필요")
        self.assertEqual(badges.columns({"error": "timed out"})[0]["label"], "동기화 실패")
        self.assertTrue(badges.columns(None)[0]["warn"])
        data = {"bars": [
            {"label": "현재 세션", "pct": 21, "pct_text": "21%", "sub": "2시간 후 재설정"},
            {"label": "모든 모델", "pct": 105, "pct_text": "100%", "sub": "(월) 오전 8:00에 재설정"},
            {"label": "extra", "pct": 1, "pct_text": "1%", "sub": ""},
        ]}
        cols = badges.columns(data, "ko", self.NOW)
        self.assertEqual(len(cols), 2)
        self.assertEqual((cols[0]["label"], cols[0]["reset"]), ("세션", "2시간 후 초기화"))
        self.assertEqual(cols[1]["pct"], 100.0)

    def test_badges_only_mode_has_no_widget_entry(self):
        app = badges.BadgeApp.__new__(badges.BadgeApp)
        app.parent_pid = 0
        app.widget_allowed = True
        with patch.object(badges, "read_json", return_value={"display": "badges", "lang": "en"}), \
                patch.object(badges.socket, "socket") as sock:
            self.assertTrue(app.housekeeping())
            self.assertFalse(app.widget_allowed)
            app.open_widget()
        sock.assert_not_called()
        self.assertEqual(app.lang, "en")

    def test_claude_only_view_shows_only_the_claude_badge(self):
        app = badges.BadgeApp.__new__(badges.BadgeApp)
        app.parent_pid = 0
        for mode, shown in (("claude", {"claude"}), ("codex", {"codex"}),
                            ("auto", {"claude", "codex"}), ("both_stacked", {"claude", "codex"})):
            with patch.object(badges, "read_json", return_value={"display": "badges", "mode": mode}):
                app.housekeeping()
            self.assertEqual(app.shown_keys, shown, mode)

    def test_level_colors_match_the_widget(self):
        self.assertEqual(badges.level_color(50), "#2F7DFF")
        self.assertEqual(badges.level_color(80), "#F5A85F")
        self.assertEqual(badges.level_color(95), "#F1707B")


class LanguageTests(unittest.TestCase):
    def test_page_reset_text_follows_the_chosen_language(self):
        en = {
            "2시간 12분 후 재설정": "Resets in 2 hr 12 min",
            "(월요일) 오전 8:00에 재설정": "Resets Mon 8:00 AM",
            "2026. 10. 24. 오후 5:10 초기화": "Resets Oct 24, 5:10 PM",
            "Resets in 2 hours": "Resets in 2 hours",
        }
        for text, expected in en.items():
            self.assertEqual(claude.localize_reset(text, "en"), expected, text)
        ko = {
            "Resets in 2 hr 12 min": "2시간 12분 후 재설정",
            "Resets Mon 8:00 AM": "(월) 오전 8:00에 재설정",
            "(월) 오전 8:00에 재설정": "(월) 오전 8:00에 재설정",
        }
        for text, expected in ko.items():
            self.assertEqual(claude.localize_reset(text, "ko"), expected, text)

    def test_reader_errors_follow_the_chosen_language(self):
        with patch.object(claude, "LANG", "en"):
            self.assertEqual(claude.t("한국어", "English"), "English")
        with patch.object(claude, "LANG", "ko"):
            self.assertEqual(claude.t("한국어", "English"), "한국어")
            # Low-level browser errors reach the widget too (Codex shows them).
            with self.assertRaises(claude.SyncError) as raised:
                claude.loopback_url("http://example.com:1/", "http")
            self.assertEqual(str(raised.exception), "브라우저 주소가 올바르지 않습니다")

    def test_english_badges_use_english_reset_text(self):
        data = {"bars": [{"label": "Current session", "pct": 5, "sub": "Resets in 2 hr 12 min"},
                         {"label": "All models", "pct": 55, "sub": "Resets Mon 8:00 AM"}]}
        cols = badges.columns(data, "en", BadgeTests.NOW)
        self.assertEqual([(c["label"], c["reset"]) for c in cols],
                         [("Session", "in 2h 12m"), ("Weekly", "Mon 8:00 AM")])


WEB_FIXTURE_BLOCKS = [
    # The weekly shared limit as the page renders it (label / value / 남음 / reset).
    ["주간 사용 한도", "35%", "남음", "2026. 9. 19. 오후 5:10 초기화"],
    # A block that is not a usage limit (must be ignored: no reset marker).
    ["Skills used", "100%"],
]


class CodexWebTests(unittest.TestCase):
    def test_codex_reuses_the_shared_sync_with_its_own_page(self):
        self.assertEqual(web.usage.PAGE_HOSTS, ("chatgpt.com", "openai.com"))
        with patch.object(web.usage, "sync_usage", return_value={"bars": []}) as shared:
            web.sync_usage()
        reader = shared.call_args.args[0]
        devtools = Mock()
        with patch.object(web, "refresh_usage", return_value={"blocks": WEB_FIXTURE_BLOCKS}):
            self.assertEqual(reader(devtools)["bars"][0]["pct"], 65.0)

    def test_web_reader_parses_page_blocks(self):
        self.addCleanup(setattr, web, "LANG", web.LANG)
        self.addCleanup(setattr, web.usage, "LANG", web.usage.LANG)
        web.LANG = web.usage.LANG = "ko"
        payload = web.make_payload({"blocks": WEB_FIXTURE_BLOCKS})
        assert len(payload["bars"]) == 1, payload
        bar = payload["bars"][0]
        assert bar["label"] == "주간 한도", bar
        assert bar["pct"] == 65.0, bar          # 35% 남음 -> 65% 사용
        assert bar["pct_text"] == "65%", bar
        assert "초기화" in bar["sub"], bar

        # English "used" wording is taken as used, not converted.
        used_block = web.parse_block(["Weekly limit", "42% used", "resets Sep 19"])
        assert used_block["used"] == 42.0, used_block
        # "left" wording is remaining -> converted.
        left_block = web.parse_block(["Weekly limit", "70%", "left", "resets Sep 19"])
        assert left_block["used"] == 30.0, left_block
        # Shared-limit note is not mistaken for the label.
        shared = web.parse_block(["Codex와 Work는 동일한 사용 한도를 공유합니다.",
                              "주간 사용 한도", "35%", "남음", "9. 19. 초기화"])
        assert shared["label"] == "주간 사용 한도", shared
        merged = web.parse_block(["사용 한도", "13%", "남음", "주간 사용 한도6일 16시간 후 초기화됩니다"])
        assert merged["label"] == "주간 사용 한도", merged
        assert merged["reset"] == "6일 16시간 후 초기화", merged
        tail = web.parse_block(["주간 사용 한도", "37%", "남음", "6일 5시간 후 초기화됩니다37% 남음"])
        assert tail["reset"] == "6일 5시간 후 초기화", tail
        assert tail["used"] == 63.0, tail
        english = web.parse_block(["Weekly limit", "37%", "left", "Resets in 6 days 37% left"])
        assert english["reset"] == "Resets in 6 days", english
        web.LANG = web.usage.LANG = "en"
        english = web.make_payload({"blocks": WEB_FIXTURE_BLOCKS})["bars"][0]
        assert english["label"] == "Weekly limit", english
        assert english["sub"] == "Resets Sep 19, 5:10 PM", english
        assert web.normalize_label("5시간 사용 한도") == "5-hour limit"
        web.LANG = web.usage.LANG = "ko"
        assert web.normalize_label("Weekly usage limit") == "주간 한도"


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
        app.display = "widget"
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

    def test_codex_syncs_through_the_browser_reader(self):
        app = self.app()
        app._load_latest = Mock(return_value={"bars": []})
        with patch.object(widget, "run_script", return_value=Mock(returncode=0, stderr="")) as run:
            app._sync_worker([widget.SOURCE_BY_KEY["codex"]], False, "en")
        self.assertIs(run.call_args.args[0], widget.CODEX_WEB_SCRIPT)

    def test_recover_restart_closes_reader_and_requests_resync(self):
        app = self.app()
        with patch.object(widget, "run_script", return_value=Mock(returncode=0, stderr="")) as run:
            app._recover_worker("restart", [widget.SOURCE_BY_KEY["claude"]], "en")
        args = run.call_args.args
        self.assertIs(args[0], widget.USAGE_SCRIPT)
        self.assertIn("--close", args)
        self.assertEqual(app.events.get_nowait()[0], "recover_done")

    def test_recover_reconnect_opens_login_without_resync(self):
        app = self.app()
        with patch.object(widget, "run_script", return_value=Mock(returncode=0, stderr="")) as run:
            app._recover_worker("reconnect", [widget.SOURCE_BY_KEY["claude"]], "en")
        self.assertIn("--connect", run.call_args.args)
        self.assertTrue(app.events.empty())

    def test_badges_only_keeps_widget_hidden_but_syncs_running_apps(self):
        app = self.app()
        app.display = "badges"
        app._known_app_keys = {"codex"}
        app.root.withdraw()
        self.assertEqual([s["key"] for s in app._visible_sources()], ["codex"])
        app.events.put(("autoshow", None))
        app._poll_events()
        self.assertEqual(app.root.state(), "withdrawn")
        # Nothing but the display setting brings the widget back: not the tray
        # icon click (toggle), the desktop shortcut or a badge (show).
        for action in ("show", "toggle"):
            app.events.put((action, None))
            app._poll_events()
            self.assertEqual(app.root.state(), "withdrawn", action)
        with patch.object(app, "_save_settings"), patch.object(app, "_update_badges"), \
                patch.object(app, "start_sync"):
            app.display_var = Mock()
            app._set_display("both")
        self.assertEqual(app.root.state(), "normal")

    def test_uninstall_removes_every_trace(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state, browser, program = root / "state", root / "ClaudePet", root / "program"
            for folder in (state / "sub", browser / "BrowserProfile", program):
                folder.mkdir(parents=True)
            (state / "settings.json").write_text('{"lang": "en"}', encoding="utf-8")
            links = [root / name for name in ("startup.lnk", "desktop.lnk")]
            for link in links:
                link.write_text("x")
            with patch.multiple(widget, STATE_DIR=state, SETTINGS_FILE=state / "settings.json",
                                BROWSER_DATA_DIR=browser, BASE_DIR=program,
                                STARTUP_LINK=links[0], DESKTOP_LINK=links[1],
                                send_control=Mock(), wait_for_exit=Mock(), run_script=Mock(),
                                stop_leftover_processes=Mock(), schedule_self_delete=Mock(),
                                messagebox=Mock(), tk=Mock()):
                widget.uninstall()
                widget.schedule_self_delete.assert_called_once_with(program, state, browser)
                self.assertIn("Uninstall complete", widget.messagebox.showinfo.call_args.args[1])
                widget.stop_leftover_processes.assert_called_once()
            self.assertFalse(state.exists())
            self.assertFalse(browser.exists())
            self.assertFalse(any(link.exists() for link in links))

    def test_badges_only_view_mode_narrows_synced_apps(self):
        app = self.app()
        app.display = "badges"
        app.mode = "codex"
        app._known_app_keys = {"claude", "codex"}
        app.root.withdraw()
        self.assertEqual([s["key"] for s in app._visible_sources()], ["codex"])

    def test_installer_creates_a_working_shortcut(self):
        installer = load("tested_install", "install.py")
        with tempfile.TemporaryDirectory(prefix="ccu shortcut '문서' ") as temp:
            link = Path(temp) / "Claude Codex Usage.lnk"
            with patch.object(installer, "STATE_DIR", Path(temp) / "state"):
                installer.create_shortcut(link, Path(sys.executable), '"%s" --watch' % installer.APP_SCRIPT, "test")
            self.assertTrue(link.exists())
            read = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
                 "$s.TargetPath; $s.Arguments; $s.WorkingDirectory"],
                env=dict(os.environ, LNK=str(link)), capture_output=True, text=True, check=True,
            ).stdout.splitlines()
            self.assertEqual(Path(read[0]).resolve(), Path(sys.executable).resolve())
            self.assertTrue(read[1].endswith("--watch"))
            self.assertEqual(Path(read[2]), Path(temp) / "state")

    def test_codex_app_is_recognised_and_claude_code_cli_is_not(self):
        rank = widget.app_rank
        self.assertEqual(rank("codex", r"C:\Apps\OpenAI.Codex\app\Codex.exe"), 0)
        self.assertEqual(rank("codex", r"C:\Apps\ChatGPT.exe"), 1)
        self.assertEqual(rank("codex", r"C:\Apps\ChatGPT Classic.exe"), 2)
        self.assertIsNone(rank("codex", r"C:\Apps\chrome.exe"))
        self.assertEqual(rank("claude", r"C:\Apps\Claude\claude.exe"), 0)
        self.assertIsNone(rank("claude", r"C:\Users\me\claude-code\claude.exe"))
        self.assertIn(("codex", "codex"), widget.APP_KEY_BY_NAME)

    def test_one_menu_drives_tray_and_widget(self):
        def flat(items):
            for entry in items:
                if entry and entry[0] == "sub":
                    yield from flat(entry[2])
                elif entry:
                    yield entry
        items = list(flat(widget.menu_spec("en", "claude", True, "badges")))
        self.assertTrue(all(entry[1] in widget.MENU_ACTIONS for entry in items))
        enabled = {entry[1]: entry[4] for entry in items}
        checked = {entry[1]: entry[3] for entry in items}
        self.assertTrue(enabled[2001] and enabled[2002])          # Claude / Codex only
        self.assertFalse(enabled[2004])                           # arrows view
        self.assertFalse(enabled[widget.SHOW_HIDE_ID] or enabled[widget.RESET_POS_ID])
        self.assertTrue(checked[2001] and checked[widget.ON_TOP_ID] and checked[widget.LANG_EN_ID])
        self.assertEqual(widget.MENU_ACTIONS[3201], ("display", "badges"))

    def test_widget_only_never_syncs_for_badges(self):
        app = self.app()
        app.display = "widget"
        app.mode = "claude"
        app._known_app_keys = {"claude", "codex"}
        self.assertEqual([s["key"] for s in app._visible_sources()], ["claude"])

    def test_moved_widget_stays_on_its_own_monitor(self):
        app = self.app()
        app.root = Mock()
        app.dragging, app.width, app.height = False, 192, 150
        app.user_moved, app.pos_x, app.bottom_anchor = True, 2500, 900
        with patch.object(widget, "monitor_work_area", return_value=(1920, 0, 3200, 1024)), \
                patch.object(widget, "work_area", return_value=(0, 0, 1920, 1040)):
            widget.UsageApp._place(app)  # self.app() stubs _place
        app.root.geometry.assert_called_with("192x150+2500+750")
        self.assertTrue(app.user_moved)

    def test_widget_on_an_unplugged_monitor_returns_to_the_default_corner(self):
        app = self.app()
        app.root = Mock()
        app.dragging, app.width, app.height = False, 192, 150
        app.user_moved, app.pos_x, app.bottom_anchor = True, 2500, 900
        with patch.object(widget, "monitor_work_area", return_value=None), \
                patch.object(widget, "work_area", return_value=(0, 0, 1920, 1040)):
            widget.UsageApp._place(app)  # self.app() stubs _place
        app.root.geometry.assert_called_with("192x150+1714+882")
        self.assertFalse(app.user_moved)

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
