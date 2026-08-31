# Changelog

All notable changes to Claude Codex Usage are documented here. Versions follow
[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

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

[0.1.0]: https://github.com/minsk8775/Claude-Codex-usage/releases
