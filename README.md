# Claude Codex Usage for Windows

[English](#english) · [한국어](#한국어)

A small always-on-top Windows widget that shows **Claude and Codex usage
together** just above the taskbar. It combines
[`claude-usage`](https://github.com/minsk8775/claude-usage) (Claude) and
[`codex-usage`](https://github.com/minsk8775/codex-usage) (Codex) into one widget
with four view modes.

```text
┌──────────────────────────┐
│ USAGE          ↻ ▾ ×     │
│ CLAUDE                   │
│ 현재 세션            73%  │
│ ██████████████████░░░░░░ │
│ 3시간 35분 후 재설정       │
│ 모든 모델             17%  │
│ ████░░░░░░░░░░░░░░░░░░░░░ │
│ CODEX                    │
│ 주간 한도             25%  │
│ ██████░░░░░░░░░░░░░░░░░░░ │
│ 6일 19시간 후 재설정       │
└──────────────────────────┘
```

## View modes

Pick a mode from the **`▾` button** (between `↻` and `×`) or by right-clicking
the notification-area icon:

- **둘 다 보기 (both, stacked)** — Claude and Codex in one window (default)
- **둘 다 (좌우 전환)** — one at a time, flip with the `‹ ›` arrows
- **Claude만** — Claude only
- **Codex만** — Codex only

---

## English

### How it reads usage

- **Claude** (`usage.py`) opens Claude's official `Settings → Usage` page in a
  dedicated Chrome/Edge profile and reads only the rendered meters. It never
  reads cookies or tokens. First use needs a one-time sign-in.
- **Codex** (`codex_usage.py`) reads the rate-limit snapshot the Codex CLI writes
  locally under `~/.codex/sessions`. No browser, no login.

Neither calls a model, so checking usage consumes no quota.

### Requirements

- Windows 10 or Windows 11
- Chrome or Edge (for the Claude meter)
- The [Codex CLI](https://github.com/openai/codex), used at least once (for the
  Codex meter)
- Python 3, or [uv](https://docs.astral.sh/uv/) (either is enough; `uv` optional)
- Git, to let the widget update itself

### Installation

```cmd
git clone https://github.com/minsk8775/Claude-Codex-usage.git
cd Claude-Codex-usage
install.cmd
```

Administrator privileges are not required. The installer creates a desktop
shortcut and a Startup entry and starts the widget once.

### First Claude connection

1. Switch to a view that shows Claude, click `↻`.
2. Sign in to Claude in the dedicated browser window that opens.
3. After `Settings → Usage` appears, click `↻` again.

Codex needs no sign-in — just have used the Codex CLI at least once.

### Controls

| Action | Control |
| --- | --- |
| Move the widget | Drag anywhere except the buttons and the resize grip |
| Resize | Drag the bottom-right grip, or `Ctrl` + mouse wheel |
| Change view mode | Click `▾`, or right-click the notification icon |
| Open the app | Double-click Claude's area → Claude app; Codex's area → Codex usage page |
| Sync now | Click `↻` |
| Hide / show | Click `×`, or left-click the notification icon |
| Always on top on/off | Right-click the notification icon → `항상 위` |
| Exit | Right-click the notification icon → `Exit` |

Percent is **used** (the bar fills as you consume quota). A moved widget keeps
its bottom edge fixed when the height changes between modes.

### Self-updating

When the folder is a Git checkout, the widget runs `git pull --ff-only` once
shortly after it starts and relaunches itself if `claude_usage.pyw`,
`usage.py`, or `codex_usage.py` changed.

### Project files

| File | Purpose |
| --- | --- |
| `claude_usage.pyw` | The combined widget UI, notification icon, view modes |
| `usage.py` | Claude usage from the official Usage page (browser) |
| `codex_usage.py` | Codex usage from local `~/.codex` session logs |
| `install.py` / `install.cmd` | Shortcut creation / installation |
| `uninstall.cmd` | Removes automatic startup and shortcuts |
| `assets/claude-usage.ico` | Widget icon |

### License

MIT

---

## 한국어

Claude와 Codex 사용량을 **한 위젯에서 함께** 작업표시줄 위에 보여주는 Windows용
도구입니다. [`claude-usage`](https://github.com/minsk8775/claude-usage)(Claude)와
[`codex-usage`](https://github.com/minsk8775/codex-usage)(Codex)를 하나로 합쳐
네 가지 보기 모드를 제공합니다.

### 보기 모드

`↻`와 `×` 사이의 **`▾` 버튼**을 누르거나 알림 영역 아이콘을 우클릭해 고릅니다:

- **둘 다 보기** — Claude·Codex를 한 창에 세로로 (기본값)
- **둘 다 (좌우 전환)** — 한 번에 하나씩, `‹ ›` 화살표로 전환
- **Claude만** / **Codex만** — 한쪽만

### 사용량을 읽는 방식

- **Claude** (`usage.py`): 전용 Chrome/Edge로 Claude 공식 `설정 → 사용량`
  페이지의 렌더링된 값만 읽습니다. 쿠키·토큰은 읽지 않으며 최초 1회 로그인 필요.
- **Codex** (`codex_usage.py`): Codex CLI가 `~/.codex/sessions`에 남긴 rate-limit
  스냅샷을 로컬에서 읽습니다. 브라우저·로그인 불필요.

모델을 호출하지 않으므로 사용량 확인으로 할당량이 소모되지 않습니다.

### 요구 사항

- Windows 10 또는 11
- Chrome 또는 Edge (Claude 미터용)
- [Codex CLI](https://github.com/openai/codex), 최소 한 번 사용 (Codex 미터용)
- Python 3 또는 [uv](https://docs.astral.sh/uv/) (둘 중 하나, `uv`는 선택)
- Git (자동 업데이트에 필요)

### 설치

```cmd
git clone https://github.com/minsk8775/Claude-Codex-usage.git
cd Claude-Codex-usage
install.cmd
```

관리자 권한은 필요 없습니다. 바탕화면·시작프로그램 바로가기를 만들고 위젯을 한 번
실행합니다.

### 최초 Claude 연결

1. Claude가 보이는 모드에서 `↻`를 누릅니다.
2. 열리는 전용 브라우저 창에서 Claude에 로그인합니다.
3. `설정 → 사용량`이 나타나면 `↻`를 다시 누릅니다.

Codex는 로그인 불필요 — Codex CLI를 한 번이라도 썼으면 됩니다.

### 버튼과 조작

| 동작 | 방법 |
| --- | --- |
| 위치 옮기기 | 버튼·크기 손잡이 제외한 아무 곳 드래그 |
| 크기 조절 | 오른쪽 아래 손잡이 또는 `Ctrl` + 마우스 휠 |
| 보기 모드 변경 | `▾` 클릭 또는 알림 아이콘 우클릭 |
| 앱 열기 | 더블클릭 — Claude 쪽→Claude 앱, Codex 쪽→Codex 사용량 페이지 |
| 즉시 동기화 | `↻` |
| 숨기기/표시 | `×` 또는 알림 아이콘 왼쪽 클릭 |
| 항상 위 켜기/끄기 | 알림 아이콘 우클릭 → `항상 위` (끄면 일반 창처럼 뒤로 내려감) |
| 완전 종료 | 알림 아이콘 우클릭 → `Exit` |

퍼센트는 **사용량 기준**(쓸수록 막대가 참)입니다. 창을 옮겨 둔 경우, 모드에 따라
높이가 바뀌어도 아래 모서리가 고정됩니다.

### 파일 구성

| 파일 | 역할 |
| --- | --- |
| `claude_usage.pyw` | 통합 위젯 UI, 알림 아이콘, 보기 모드 |
| `usage.py` | Claude 공식 Usage 페이지에서 사용량 읽기(브라우저) |
| `codex_usage.py` | 로컬 `~/.codex` 세션 로그에서 Codex 사용량 읽기 |
| `install.py` / `install.cmd` | 바로가기 생성 / 설치 |
| `uninstall.cmd` | 자동 실행·바로가기 제거 |
| `assets/claude-usage.ico` | 위젯 아이콘 |

### 라이선스

MIT
