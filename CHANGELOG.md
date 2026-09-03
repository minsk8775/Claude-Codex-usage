# Changelog

All notable changes to Claude Codex Usage are documented here. Versions follow
[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

## [Unreleased]

### Fixed
- Verify browser executable and Windows process creation time before shutdown;
  terminate the verified process handle so a reused PID cannot close another app.
- Keep model-specific Codex limit buckets out of the general usage display.
- Show the actual Codex snapshot time and mark expired or over-five-minute-old
  values as stale instead of presenting them as current usage.
- Preserve manual hiding while watched apps stay open, including background
  watcher checks; reopen only when a watched app starts again.
- Replay pending sync requests after completion using the latest view/language,
  preserving manual sign-in intent. Failed readers no longer reuse a success cache.

### Security
- Restrict UDP control input to explicit external commands, discard oversized
  packets and malformed bytes, and bound the UI event queue and processing batch.
- Read log lines in bounded chunks; reject malformed event shapes, deeply nested
  JSON and invalid numeric values without losing earlier valid snapshots.
- Validate loopback DevTools endpoints, disallow HTTP redirects/proxies, verify
  WebSocket ports, and bound HTTP/WebSocket response sizes.
- Restrict update checks to the exact official origin and its `main` branch,
  without fetching tags/submodules or executing downloaded code.
- Correct the security documentation: a localhost Origin header is not client
  authentication, and older browser state without process identity is not killed.

### Tests
- Add offline regression tests covering the fixes and untrusted input boundaries.

## [0.6.2] - 2026-09-02

### Fixed
- **앱 실행 시 위젯 자동 표시가 안 되던 문제**: 감시자(watcher)가 갱신되지 않던
  것이 원인이었습니다.
  - `install.cmd`(install.py)가 **자기 앱의 기존 위젯·감시자를 먼저 종료**한 뒤
    새로 띄우도록 수정. 이전에는 옛 감시자가 포트(47672)를 독점(EXCLUSIVEADDRUSE)해
    새 감시자가 바인딩에 실패하고 죽어, `install.cmd`를 다시 돌려도 감시자가 옛
    코드로 남아 있었습니다.
  - 감시자가 시작 시 포트 바인딩을 **몇 초간 재시도**하도록 해, 재설치 중 포트가
    풀리는 짧은 시간을 넘기고 반드시 뜨게 했습니다.
  - Claude/ChatGPT 데스크톱 앱 감지를 정확한 exe 이름(`chatgpt.exe`) 대신
    **부분 문자열(`claude`/`chatgpt`)** 매칭으로 바꿔, 빌드에 따라 실행 파일명이
    달라도 감지되게 했습니다(더블클릭 앱 열기와 동일한 방식).

## [0.6.1] - 2026-09-02

### Fixed
- **반복 로그인 회귀 수정**: 0.5.0에서 동기화가 끝날 때마다 백그라운드 브라우저를
  종료(`close_browser`)하도록 한 변경이, 매 동기화마다 브라우저를 새로 띄우게 만들어
  Claude 로그인 세션이 유지되지 않았습니다(Claude가 인증 토큰을 갱신하는데, 종료 시
  갱신분이 유실됨). 그 결과 로그인해도 계속 "로그인 필요"가 뜨고 새 브라우저 창이
  열렸습니다. 이제 숨겨진 브라우저를 동기화 사이에 **계속 유지**하고 위젯 종료 시에만
  닫습니다. 디버그 포트는 `--remote-allow-origins=http://localhost` origin 제한으로
  이미 보호되므로 보안 저하는 없습니다.

## [0.6.0] - 2026-09-02

### Added
- **한국어 / 영어 전환**: 우클릭(창 아무 곳) 및 알림 아이콘 메뉴에 **`언어
  (Language)`** 하위 메뉴 추가 — `한국어` / `English` 선택. 보기 모드·항상 위·
  표시/숨김·종료 등 메뉴 문구, 업데이트 배지, 상태 문구가 모두 번역됩니다. 전환하면
  리더 스크립트(`usage.py`·`codex_usage.py`)가 `--lang`으로 라벨(현재 세션/모든 모델,
  주간 한도 등)과 재설정 문구를 새 언어로 다시 생성합니다. 선택은 `settings.json`의
  `lang`에 저장됩니다.
  - Claude의 재설정 문구는 Claude 페이지에서 읽어 오므로 Claude 계정 언어를 따릅니다.

## [0.5.0] - 2026-09-02

### Security
- **자동 업데이트 제거 → 알림 방식으로 전환**: 위젯이 코드를 자동으로 내려받아
  실행하지 않습니다. 시작 시 읽기 전용 확인(`git fetch`, checkout 없음)만 하고, 새
  버전이 있으면 헤더에 빨간 **`● 업데이트 필요`** 배지를 띄웁니다. 클릭하면 GitHub
  저장소가 열려 사용자가 직접 확인·설치(`git pull` 후 `install.cmd`)합니다. 확인은
  `origin`이 HTTPS 공식 저장소일 때만 이뤄지며, `CLAUDE_CODEX_NO_UPDATE=1` 또는
  `.noupdate` 파일로 끌 수 있습니다. 조용한 자동 코드 실행이 없어 저장소가 탈취돼도
  임의 코드가 실행되지 않습니다.
- **브라우저 디버그 포트 origin 제한**: `--remote-allow-origins=*` → `http://localhost`.
  악성 웹 페이지가 DevTools 포트에 붙는 것(DNS rebinding 등)을 차단합니다. 포트는
  기존처럼 loopback 전용이며, 동기화가 끝나면 브라우저를 닫아 포트를 남기지 않습니다.
- **Codex 로그 파싱 방어**: 비정상적으로 긴 rollout 줄을 파싱 전에 건너뛰어
  (`MAX_LINE_CHARS`) 손상·악성 파일이 메모리를 소모하지 못하게 합니다.
- 보안 정책 문서 **`SECURITY.md`** 추가, README에 보안 섹션 추가.

### Notes
- 제어 포트(UDP 47671/47672)는 계속 loopback 전용이며 64바이트 상한과 고정 명령
  화이트리스트로만 처리됩니다. 모든 외부 프로세스 실행은 셸 없이 argv 리스트로
  호출되고, 앱 실행 대상(AUMID·URL)은 하드코딩 상수입니다.

## [0.4.0] - 2026-09-01

### Added
- **자동 보기 모드**(새 기본값): 실행 중인 앱에 맞춰 뷰가 바뀝니다. Claude만
  켜져 있으면 Claude 사용량만, Codex(ChatGPT)만 켜져 있으면 Codex만, 둘 다 켜져
  있으면 둘 다(세로) 보기로 자동 전환. **하나를 끄면 나머지 하나만 보이고, 둘 다
  끄면 창이 자동으로 닫히며(숨김), 다시 앱을 켜면 창이 복구**됩니다. 물론 트레이/
  `▾`/우클릭 메뉴에서 특정 모드로 고정할 수도 있습니다.
- **창 어디서나 우클릭** 시 트레이(작업표시줄) 우클릭과 동일한 메뉴(보기 모드 ·
  항상 위 · 표시/숨김 · 종료)가 나옵니다.

### Changed
- 백그라운드 감시자가 Claude 또는 ChatGPT 데스크톱 앱 실행을 감지하면 위젯을
  띄웁니다. 감시자는 별도 프로세스라, 이 버전을 적용하려면 **`install.cmd`를 다시
  실행**하거나 재부팅해 최신 감시자로 교체해야 합니다.

## [0.3.0] - 2026-08-31

### Added
- 더블클릭이 **항상 앱을 엽니다.** Claude/ChatGPT 데스크톱 앱이 실행 중이면
  포커스하고, 꺼져 있으면 AUMID(`shell:AppsFolder`)로 **직접 실행**합니다.
  (두 앱 모두 Microsoft Store 앱이라 exe 직접 실행이 안 되어 AUMID로 띄웁니다.)
  앱이 설치돼 있지 않을 때만 사이트로 폴백합니다.
- **앱 켜지면 위젯 자동 표시**: 백그라운드 감시자가 Claude/ChatGPT 데스크톱 앱
  실행을 감지하면 위젯을 띄웁니다. (감시자는 2초마다 프로세스 목록만 확인 —
  CPU·메모리 부담 거의 없음)
- 옛 standalone 위젯(claude-usage·codex-usage) 잔재를 정리하는
  **`cleanup-legacy.cmd`** 추가. 설치 시에도 자동으로 옛 시작/바탕화면 바로가기를
  제거해 부팅 시 옛 버전이 뜨지 않게 합니다.

## [0.2.0] - 2026-08-31

### Added
- 트레이(작업표시줄 알림) 우클릭 메뉴에 **"항상 위 (Always on top)"** 토글 추가.
  끄면 일반 창처럼 다른 창 뒤로 내려갈 수 있고, 설정은 저장됩니다.

### Changed
- Codex 쪽 더블클릭이 사용량 페이지 대신 **실행 중인 ChatGPT 앱**을 엽니다.
  ChatGPT와 ChatGPT Classic이 모두 켜져 있으면 ChatGPT를 우선하며, 둘 다 실행
  중이 아니면 사용량 페이지로 폴백합니다. (Claude 쪽은 설치돼 있으면 Claude 앱,
  없으면 claude.ai — 기존과 동일)

## [0.1.0] - 2026-08-31

최초 버전. `claude-usage`와 `codex-usage`를 하나의 위젯으로 합친 통합형입니다.

### Added
- 한 위젯에서 **Claude와 Codex 사용량을 함께** 표시.
- 보기 모드 4종 (기본값: **둘 다 보기**): 둘 다 세로로 / 둘 다 좌우 화살표 전환 /
  Claude만 / Codex만. `↻`와 `×` 사이의 `▾` 버튼 또는 트레이 우클릭으로 선택하며,
  선택은 저장됩니다.
- `usage.py`: Claude 공식 Usage 페이지를 전용 브라우저로 읽는 리더.
- `codex_usage.py`: Codex CLI가 `~/.codex/sessions`에 남긴 rate-limit 스냅샷을
  읽는 로컬 리더(브라우저·로그인 불필요, `--self-test` 지원).
- 더블클릭 시 클릭한 쪽에 맞는 앱(Claude 앱 / Codex 사용량 페이지)이 열림.
- 반투명 창(불투명도 약 85%), 창을 옮겨 둔 경우 높이 변화 시 아래 모서리 고정.

[0.6.2]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.6.1]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.6.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.5.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.4.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.3.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.2.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.1.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
