# 개발 히스토리 (Development History)

Claude Codex Usage 위젯의 커밋 기준 개발 이력입니다. 버전별 요약은
[`CHANGELOG.md`](CHANGELOG.md), 전체 코드 이력은 `git log`가 정본입니다.
아래는 시간순(오래된 → 최신) 흐름을 사람이 읽기 쉽게 정리한 것입니다.

> 기준: GitHub `main` 브랜치. 현재 최신 커밋 `6a1aaa1` (2026-09-14).

## 1. 통합 위젯 출발 (2026-08-31 ~ 09-01)

- `84004cb` **0.1.0** — Claude·Codex 사용량을 한 위젯에 합친 통합형. 보기 모드 4종.
- `116f797` — 트레이 메뉴에 "항상 위(Always on top)" 토글 추가.
- `0df3342` — Codex 영역 더블클릭 시 사이트가 아니라 **ChatGPT 앱**을 열도록.
- `d1f3c77` — Claude 데스크톱 앱을 더 정확히 찾은 뒤 없을 때만 사이트로 폴백.
- `f6c7b95` — 항상 데스크톱 앱을 열고, 앱 실행 시 위젯 자동 표시, 옛 위젯 정리.
- `1cc69cf` — **자동(auto) 보기 모드** + 창 우클릭 메뉴 추가.
- `67ad47c` — 자동 모드가 앱 표시 상태를 따라감(둘 다 닫히면 숨김, 열리면 복구).

## 2. 보안 강화 & 업데이트 방식 전환 (2026-09-02)

- `c9dd94b` — **보안 하드닝**: self-update 제한, 디버그 포트 잠금, 방어적 파싱.
- `e158a4f` — 자동 업데이트 제거 → **알림형 "● 업데이트 필요" 배지**로 전환
  (다운로드한 코드를 자동 실행하지 않음 = 공급망 RCE 경로 제거).
- `1a3f462` — 우클릭 메뉴에 **한국어/영어 전환** 추가.
- `5c484ce` — README에 위젯/메뉴 스크린샷(`assets/screenshot.svg`) 추가.

## 3. 실사용 버그 수정 (2026-09-02 ~ 09-03)

- `d492654` — **반복 로그인 수정**: 동기화마다 브라우저를 닫던 동작을 제거해
  숨은 브라우저를 계속 살려 로그인 세션을 유지(토큰 갱신 유실 방지).
- `a5f6cad` — **앱 실행 시 자동 표시 수정**: `install.cmd`가 자기 감시자를 먼저
  종료 후 재시작, 감시자 포트 바인딩 재시도, 앱 프로세스 부분 문자열 매칭.
- `07ab5d1` — **사용량 정확도 + 로컬 제어 경계 강화**: 모델별 Codex 버킷 제외,
  스냅샷 기록 시각 표시 및 5분 초과/만료 값 stale 표시, UDP 제어 입력 제한,
  브라우저 종료 시 프로세스 신원 검증, 회귀 테스트 스위트(`tests/`) 추가.

## 4. 최신 (2026-09-14)

- `6a1aaa1` — **Claude "동기화 실패 (timed out)" 수정**: 화면 밖 숨긴 리더 창을
  Chrome이 스로틀해 Claude 페이지(SPA + Cloudflare)가 멈추던 문제를, 스로틀 방지
  플래그(`--disable-background-timer-throttling`,
  `--disable-backgrounding-occluded-windows`, `--disable-renderer-backgrounding`)
  추가 + CDP 소켓 타임아웃 10초 → 25초로 해결.

---

## 참고

- **정본은 GitHub `main`**입니다. 최신 여부는 `git fetch` 후
  `git log --oneline -1 origin/main`으로 언제든 확인할 수 있습니다.
- 업데이트 적용: 리포 폴더에서 `git pull` 후 `install.cmd` (감시자까지 갱신).
- 사용법·보안·언어 등 상세는 [`README.md`](README.md), [`SECURITY.md`](SECURITY.md),
  [`CHANGELOG.md`](CHANGELOG.md) 참고.
