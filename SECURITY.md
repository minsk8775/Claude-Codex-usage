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

1. **The upstream Git repository** (for self-update). See below.
2. **The local machine.** Anything already running as your user could tamper with
   the checkout or the browser profile; that is outside what a user-level tool can
   defend against.

## Hardening applied

### Updates are notify-only — never auto-installed
The widget does **not** download and run new code on its own. Automatically
executing freshly pulled code would be the highest-impact path, so it was removed:

- Shortly after start, the widget does a single **read-only** check: `git fetch`
  (which updates remote-tracking refs but checks nothing out), then compares your
  `HEAD` with the upstream branch. No fetched code is executed.
- The check runs **only** when `origin` is the project's own HTTPS URL
  (`https://github.com/minsk8775/claude-codex-usage`). A repointed or forked
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
loopback port. It passes `--remote-allow-origins=http://localhost`, so only this
app's local client can attach — a malicious web page cannot reach the debug port
(including via DNS-rebinding). The browser is shut down after each sync so the port
is not left listening between refreshes. No `--disable-web-security`,
`--load-extension`, or `--remote-debugging-address` override is used.

### Local control ports are loopback-only with a fixed command set
The widget and its background watcher accept small UDP control messages on
`127.0.0.1:47671` / `47672` (show / hide / exit / switch view mode). Messages are
capped at 64 bytes and dispatched through a fixed whitelist of actions — they are
never passed to a shell, `eval`, or `exec`. The ports are bound to loopback and are
not reachable from other hosts.

### No shell, no injected input in process launches
Every external process (`git`, `powershell`, `explorer.exe`, the Python readers,
the target apps) is started with an argument **list**, never `shell=True` and never
a shell string. App launch targets (AUMIDs and fallback URLs) are hard-coded
constants, so no untrusted value reaches a command line.

### Defensive parsing of local session logs
`codex_usage.py` treats `~/.codex` rollout files as untrusted input: every line is
wrapped in `try/except`, oversized lines are skipped before parsing
(`MAX_LINE_CHARS`) to bound memory, and malformed JSON is ignored rather than
crashing the widget.

### Secrets stay out of Git
`.gitignore` excludes the generated snapshots (`latest.json`, `codex_latest.json`),
`error.log`, and `*.credentials*` / `*.local.*`, so nothing derived from your
session is ever committed.

## Residual risks (accepted)

- **Local processes can send control messages.** Any process running as your user
  can send `show`/`hide`/`exit`/mode-switch UDP packets to the loopback control
  ports. Impact is limited to showing, hiding, or closing the widget — no data
  exfiltration and no code execution. Defending against same-user local processes
  is out of scope for a user-level widget.
- **Applying an update trusts the upstream maintainer.** The widget never installs
  updates automatically, so a compromised repository cannot push code to your
  machine on its own. The residual trust is only in what *you* choose to install
  when you run `git pull` after clicking the badge — review the diff on GitHub
  first, exactly as you would for any Git project.
