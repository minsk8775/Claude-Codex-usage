# Changelog

All notable changes to Claude Codex Usage are documented here. Versions follow
[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

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

[0.3.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.2.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
[0.1.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
