# Security Policy

Claude Codex Usage is a local, single-user Windows widget. It reads your Claude
and Codex usage numbers and shows them above the taskbar. This document explains
its trust model, the hardening it applies, and how to report a problem.

## Reporting a vulnerability

Please open a private report through GitHub Security Advisories on
[`minsk8775/claude-codex-usage`](https://github.com/minsk8775/claude-codex-usage/security/advisories/new),
or open an issue that describes the impact without a working exploit. Expect an
acknowledgement within a few days.

## What the app does and does not touch

- **Claude usage** (`usage.py`) opens Claude's official *Settings → Usage* page in
  a dedicated Chrome/Edge profile and reads only the rendered meter values via the
  DevTools protocol. It **never reads cookies, tokens, `localStorage`, or any
  credential file.** Your sign-in lives only inside that browser profile directory.
- **Codex usage** (`codex_usage.py`) reads the rate-limit snapshot the Codex CLI
  already wrote under `~/.codex/sessions`. No browser, no network, no login.
- Neither reader calls a model, so checking usage never consumes quota.

## Trust model

The app runs entirely on your machine with your user privileges. It makes no
inbound network connections and opens no ports reachable from off-host. Its trust
boundaries are:

1. **The upstream Git repository** (for update notifications). See below.
2. **The local machine.** Anything already running as your user could tamper with
   the checkout or the browser profile; that is outside what a user-level tool can
   defend against.

## Hardening applied

### Updates are notify-only — never auto-installed
The widget does **not** download and run new code on its own. Automatically
executing freshly pulled code would be the highest-impact path, so it was removed:

- Shortly after start, the widget fetches only the official `main` branch, with
  tags and submodule fetching disabled, then compares `HEAD` with `FETCH_HEAD`.
  Only an ahead commit that changes application or installer code triggers a
  notification. Git metadata changes, but no checkout, install or execution of
  fetched code takes place.
- The check runs **only** when `origin` is the project's own HTTPS URL
  (`https://github.com/minsk8775/claude-codex-usage`, optionally ending in `.git`).
  Subpaths and other URLs are rejected. A repointed or forked
  `origin` produces no update prompt at all.
- If newer widget code exists, a `● 업데이트 필요` badge appears in the header.
  Clicking it opens the repository on GitHub so you can review the diff and install
  it yourself (`git pull` then `install.cmd`). The install is always a deliberate,
  user-initiated step.

**Turn the check off** by setting the environment variable
`CLAUDE_CODEX_NO_UPDATE=1` or creating an empty file named `.noupdate` next to
`claude_usage.pyw`. The widget then never contacts the remote for updates.

### Browser debug port is loopback-only and origin-restricted
`usage.py` drives a Chrome/Edge instance over the DevTools protocol on a random
loopback port. It passes `--remote-allow-origins=http://localhost` to reject other
WebSocket origins. **This is not client authentication:** local programs can set
the same Origin header and access DevTools. The dedicated browser is kept running
between syncs to preserve its sign-in session.

The reader accepts only numeric loopback addresses (normalizing `localhost` to
`127.0.0.1` without DNS), refuses credentials in endpoint URLs, disables HTTP
proxies and redirects, and requires page WebSockets to use the expected debug
port. HTTP responses and complete WebSocket messages, including fragmented
messages, have a 2,000,000-byte limit. No
`--disable-web-security`, `--load-extension`, or `--remote-debugging-address`
override is used.

### Browser shutdown verifies process identity
New browser launches record the Windows process creation time alongside the PID,
executable and dedicated profile path. Shutdown opens one process handle and
checks its creation time and executable before terminating **that same handle**.
A reused PID, identity mismatch, missing identity, or unexpected profile is not
terminated. Older saved state without creation time is deliberately left alone;
the old dedicated usage browser may need to be closed manually once after an
upgrade. The interactive sign-in browser is not automatically terminated.

### Local control ports are loopback-only with a fixed command set
The widget and its background watcher accept small UDP control messages on
`127.0.0.1:47671` / `47672`. The widget accepts only the exact ASCII commands
`show`, `hide`, `toggle`, and `exit`; the watcher accepts only `exit`. Internal
worker events such as `sync_result` cannot be injected through these sockets.
Malformed and oversized messages are discarded. The widget's queue and the
number of events handled per UI tick are bounded. Commands are never passed to a
shell, `eval`, or `exec`. The ports are bound to loopback.

### No shell, no injected input in process launches
Every external process (`git`, `powershell`, `explorer.exe`, the Python readers,
the target apps) is started with an argument **list**, never `shell=True` and never
a shell string. App launch targets (AUMIDs and fallback URLs) are hard-coded
constants, so no untrusted value reaches a command line.

### Defensive parsing of local session logs
`codex_usage.py` reads rollout lines in bounded chunks and discards the entire
oversized line, so a large line is never allocated in full. Malformed/deeply
nested JSON, invalid shapes, non-finite percentages and invalid timestamps are
ignored. Only actual `token_count` events are accepted, not matching objects
nested in tool output. Model-specific limit IDs cannot replace the general
Codex bucket. Recorded timestamps and stale indicators make the limits of local
snapshots visible.

### Secrets stay out of Git
`.gitignore` excludes the generated snapshots (`latest.json`, `codex_latest.json`),
`error.log`, and `.credentials.json` / `*.local.*`. The dedicated profile lives
outside the checkout. Review staged files before publishing; ignore rules are
not a substitute for checking what is being committed.

## Residual risks (accepted)

- **Local processes can send control messages.** Any process running as your user
  can send `show`/`hide`/`toggle`/`exit` UDP packets to the loopback control
  ports. Impact is limited to showing, hiding, or closing the widget — no data
  exfiltration and no code execution. Defending against same-user local processes
  is out of scope for a user-level widget.
- **DevTools and the browser profile require local trust.** A process running as
  your user can attach to the dedicated browser or read its profile. Origin
  checks and process-identity checks do not protect against a hostile program
  that can already modify your files. Do not use this profile for other browsing.
- **Dependencies and the host are trusted.** Installation obtains `pywin32` from
  the configured Python package index. Windows, Python, Git, Chrome/Edge and
  installer dependencies are outside this repository's security boundary.
- **Applying an update trusts the upstream maintainer.** The widget never installs
  updates automatically, so a compromised repository cannot push code to your
  machine on its own. The residual trust is only in what *you* choose to install
  when you run `git pull` after clicking the badge — review the diff on GitHub
  first, exactly as you would for any Git project.
