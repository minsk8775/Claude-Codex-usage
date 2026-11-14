# Changelog

All notable changes to Claude Codex Usage are documented here. Versions follow
[Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.
Each version lists its changes in Korean first, then in English (0.7.0 is in
English only).

이 프로젝트의 모든 주요 변경 사항을 적습니다. 버전마다 한국어 다음에 영어로 적습니다
(0.7.0은 영어로만 적혀 있습니다).

## [0.9.3] - 2026-11-14

### Changed
- **위젯도 오래된 숫자를 회색으로 표시합니다**: 배지처럼, 3분 넘게 갱신되지 않은 숫자(켤 때
  보이는 이전 캐시, 계속 실패하는 동기화)는 회색입니다.
- **Codex 초기화 시간을 Claude처럼 요일과 시각으로 보여 줍니다**: 사용량 페이지의 날짜
  (`2026. 10. 24. 오후 5:10`)를 남은 시간(`2일 2시간 후`) 대신 Claude의 주간 초기화처럼
  `(토) 오후 5:10`으로 보여 줍니다(위젯·배지 모두, `에 초기화` 없이). 일주일 이상 남았으면
  날짜도 붙입니다(`10/31 (토) 오후 5:10`). 영어는 `Sat 5:10 PM`.
- **ZIP으로 설치해도 업데이트 알림이 뜹니다**: git이 없는 설치는 시작할 때 GitHub 최신 릴리스
  버전과 비교해(읽기만 함) 새 버전이면 `● 업데이트 필요` 배지를 띄우고, 누르면 릴리스
  페이지가 열립니다.
- `설치된 앱`의 조용한 제거(`--uninstall --quiet`)를 지원합니다. 확인·완료 창 없이 지웁니다.
- GitHub의 Windows 테스트가 실제로 설치한 뒤 조용히 제거하고, 바로가기·설치된 앱 항목·
  설정·로그인 정보·프로그램 폴더·실행 중인 프로세스가 하나도 남지 않는지 확인합니다.
- `CHANGELOG.md`의 모든 버전에 영어 설명을 함께 적었습니다.
- **새 아이콘**: 위에 Claude 느낌의 주황 불꽃, 아래에 Codex를 뜻하는 터미널 `>_`, 가운데에
  `Usage`. 작은 크기(32px 이하)에서는 글자 없이 두 표시만 위아래로 둡니다. 두 회사 로고를
  그대로 쓰지 않고 직접 그렸습니다(`tools/make_icon.py`).

### Fixed
- **우클릭 한 번에 `완전 종료`가 눌려 꺼지던 문제**: 메뉴를 버튼을 누르는 순간 열어서, 메뉴가
  커서 아래에 뜨면 버튼을 떼는 동작이 그 자리의 항목을 눌렀습니다. 화면 아래쪽에서는 메뉴가
  위로 펼쳐져 맨 아래 항목인 `완전 종료`가 커서 밑에 왔습니다. 이제 위젯·배지의 우클릭과
  `▾` 버튼 메뉴는 버튼을 뗄 때 열리고, `완전 종료`는 확인 창을 거칩니다.

### English

#### Changed
- **The widget greys out old numbers too**: as on the badges, numbers not
  refreshed for over 3 minutes (the cache shown at start, syncs that keep
  failing) are drawn grey.
- **Codex reset times look like Claude's: weekday and time**: the page's date
  (`2026. 10. 24. 오후 5:10`) is shown as `Sat 5:10 PM` (`(토) 오후 5:10` in
  Korean), like Claude's weekly reset, instead of time left (`in 2d 2h`). A reset
  a week or more away also gets its date (`Sat Oct 31, 9:05 AM`).
- **ZIP installs get update notices too**: without git, the widget compares
  its version with the latest GitHub release at startup (read-only) and shows
  the `● Update available` badge, which opens the release page.
- Quiet uninstall from `Installed apps` (`--uninstall --quiet`), with no
  confirmation or completion dialog.
- The Windows tests on GitHub now really install the app, remove it with the
  quiet uninstaller and check that no shortcut, Installed apps entry, settings,
  sign-in data, program folder or running process is left.
- Every version in `CHANGELOG.md` now has an English description too.
- **New icon**: a Claude-style orange spark on top, a terminal `>_` for Codex
  below and `Usage` between them; at 32 px and smaller only the two marks. The
  marks are drawn for this app (`tools/make_icon.py`), not copied logos.

#### Fixed
- **A single right-click could hit `Quit`**: menus opened when the button was
  pressed, so a menu that appeared under the cursor took the button release as a
  click on the item there; near the bottom of the screen the menu opens upward
  and that item was `Quit`, the last one. Right-click menus on the widget and
  badges and the `▾` button menu now open on release, and `Quit` asks first.

## [0.9.2] - 2026-11-09

### Changed
- **배지를 우클릭하면 위젯·알림 아이콘과 같은 전체 메뉴가 뜹니다**: 배지만 표시할 때도 보기
  방식, 표시 방식, 언어, 동기화 문제 해결, 종료를 배지에서 바로 고릅니다.
  `배지 위치 초기화`는 이 메뉴에 들어 있습니다(배지를 쓸 때만 보임).
- **Python이 없어도 설치됩니다**: uv도 Python도 없으면 `install.cmd`가 Python 3.12를 이
  사용자 계정에 설치하고 이어서 설치합니다. `winget`으로 먼저 시도하고, 없거나 실패하면
  python.org 공식 설치 파일을 받아 설치합니다(ARM PC는 ARM용). PATH에 없는 설치된
  Python도 찾아 쓰고, Microsoft Store로만 연결되는 `python` 바로가기는 Python으로 치지 않습니다.
- **메뉴의 `제거`를 `완전 종료`로 바꾸고, 제거는 Windows `설치된 앱`에서 합니다**:
  - `종료 (앱을 켜면 다시 표시)`: 위젯만 닫습니다. 다음에 Claude·ChatGPT 앱을 켜면 다시 뜹니다.
  - `완전 종료 (자동 실행 끔)`: 감시자까지 꺼서 재부팅해도 다시 뜨지 않습니다. 바탕화면
    바로가기로 위젯을 열면 자동 실행이 다시 켜집니다.
  - 설치하면 `설정 → 앱 → 설치된 앱`(제어판 `프로그램 제거`)에 등록되어, 다른 프로그램처럼
    제거합니다(확인 창을 거침). 바로가기·설정·로그인 정보·프로그램 폴더와 이 등록 항목까지
    지웁니다. `uninstall.cmd`도 같은 제거를 실행합니다.
- Pin GitHub Actions to verified commit SHAs and test settings replacement and
  replacement failures using temporary files.

### Fixed
- **위젯을 우클릭해도 메뉴가 뜨지 않던 문제(0.9.1)**: 메뉴를 하나로 합치면서 하위 메뉴
  (표시 방식·언어·동기화 문제 해결)를 만들 때 오류가 나 메뉴 전체가 열리지 않았습니다.
  그래서 `다시 로그인` 같은 복구 메뉴도 쓸 수 없었습니다. 위젯 메뉴를 실제로 열고 모든
  항목을 눌러 보는 Windows 테스트를 추가했습니다.
- 백그라운드 전용 브라우저 창을 1×1 대신 일반 크기(1280×900)로 띄웁니다(보이지 않는
  데스크톱에서 돌아 화면에는 안 보임). 사용량을 못 읽으면 그때 열린 페이지의 주소와 제목을
  `error.log`에 남깁니다.
- **Codex 한도를 못 읽던 문제(주소 변경)**: ChatGPT 사용량 페이지가 `개요`/`사용량 분석`
  탭으로 나뉘면서, 리더가 열던 주소가 한도가 없는 `사용량 분석`(`?tab=analytics`)으로
  열렸습니다. 한도가 있는 `https://chatgpt.com/settings/usage?tab=overview`로 바로 엽니다.
  위젯에서 Codex 웹사이트를 열 때도 이 주소를 씁니다.
- **언어를 바꿔도 오류 문구가 이전 언어로 남던 문제**: 오류 문구는 리더가 실행될 때의 언어로
  저장되는데, 다음 동기화가 끝날 때까지 그대로 보였습니다. 언어를 바꾸면 바로 새 언어의
  `동기화 중…`으로 바꿔 보여 줍니다.
- **Claude가 계속 `공식 사용량 동기화 실패`(사용량 브라우저를 시작하지 못했습니다)이던 문제**:
  예전에 띄운 Claude 전용 브라우저가 남아 프로필을 붙잡고 있으면, 새로 띄운 브라우저가 그쪽에
  넘기고 바로 꺼져 매번 실패했습니다. 브라우저 시작이 실패했을 때와 `리더 브라우저 재시작`
  때, 이 프로필을 쓰는 남은 전용 브라우저를 닫고 다시 띄웁니다(평소 쓰는 Chrome은 건드리지
  않음). 남은 브라우저를 찾는 일은 몇 초씩 걸려서 평소에는 하지 않습니다.
- **오래된 사용량이 최신처럼 보이던 문제**: 리더가 시간 제한에 걸려 중간에 끝나면 이전 값이
  캐시에 그대로 남아, 배지가 동기화가 멈춘 줄 모르고 옛 숫자를 계속 보여 줬습니다. 3분 넘게
  갱신되지 않은 숫자는 배지에 회색으로 표시합니다. 리더의 시간 제한도 60초에서 150초로
  늘려(페이지를 새로 불러오고 보안 확인을 기다리며 두 번까지 시도하는 시간) 중간에 끊기는
  일을 줄였습니다.
- **보안 확인(Cloudflare) 화면에서 동기화가 실패하거나 로그인이 풀리던 문제**: Claude는 이
  화면을 바로 로그아웃으로 보고 다시 로그인하게 했고, Codex는 그냥 실패했습니다. 이제 보통
  몇 초 안에 저절로 통과되므로 25초를 더 기다리고, 그래도 남아 있으면 `보안 확인 필요`를
  띄웁니다. ↻를 누르면 열리는 창에서 한 번 통과하면 됩니다.
- **`종료`하면 앱을 켜도 위젯이 다시 안 뜨던 문제**: 종료가 자동 실행 설정까지 꺼 버렸습니다.
  이제 종료는 위젯만 닫고, 다음에 Claude·ChatGPT 앱을 켜면 다시 뜹니다.
- **보안: 같은 PC를 쓰는 다른 Windows 계정이 리더 브라우저에 접근할 수 있던 문제**: 리더
  브라우저의 디버그 포트는 PC 안에서만 열리지만, 그 PC에 로그인한 다른 계정도 접근할 수
  있었습니다. 다른 계정이 로그인해 있으면 동기화가 끝날 때마다 브라우저를 닫아, 포트가
  동기화하는 몇 초 동안만 열리게 합니다(혼자 쓰는 PC는 지금처럼 켜 둡니다).
- **ChatGPT 로그인이 풀린 것으로 잘못 판단할 수 있던 문제**: 사용량 페이지가 뜨는 도중
  화면 글자에 `로그인`이 있으면 로그인 페이지로 보고 연결을 끊을 수 있었습니다. 이제 설정
  페이지를 벗어나 로그인·홈 화면으로 갔을 때만 로그인 필요로 판단합니다.
- **보안: 내려받은 Python 설치 파일을 확인 없이 실행하던 문제**: python.org에서 받은 설치
  파일은 Python Software Foundation의 유효한 디지털 서명이 있을 때만 실행합니다.
- **Codex 사용량이 실제보다 낮게(예전 값으로) 보이던 문제**: 리더가 백그라운드 브라우저에
  이미 열려 있던 사용량 페이지를 그대로 읽었는데, 이 페이지는 스스로 숫자를 갱신하지 않아
  브라우저를 띄운 때의 값이 계속 보였습니다(실제 12%인데 8%). 동기화할 때마다 페이지를
  새로 불러와 읽습니다. Claude는 원래 페이지의 새로고침 버튼을 눌러 읽어 해당 없습니다.
- **앱을 켤 때 ChatGPT 창에 Codex 배지가 안 뜨던 문제**: ChatGPT 앱은 시작하면서 잠깐
  다른 창을 띄웠다 숨기는데, 배지가 그 숨은 창을 계속 따라가 표시 방식을 바꿔(배지 도우미가
  다시 시작돼야) 나타났습니다. 따라가던 창이 화면에 없으면 1초마다 앱 창을 다시 찾습니다.
- **배지만 표시할 때 앱을 켜면 Codex 사용량이 비어 있던 문제**: 위젯이 시작하면서 Claude와
  Codex를 차례로 읽는데, 매번 남은 브라우저부터 찾느라 뒤 순서인 Codex가 시간 제한(60초)을
  넘겨 실패했고, 다음 동기화는 2분 뒤였습니다. 이제 그 검사를 실패했을 때만 하고, 읽기에
  실패한 앱은 20초 뒤에 다시 읽습니다(연속 두 번까지).
- **보안: 제거가 다른 파일이 든 폴더까지 지울 수 있던 문제**: 제거는 프로그램 폴더를 통째로
  지우는데, 앱 파일을 `다운로드`처럼 다른 파일이 있는 곳에 바로 넣어 두면 그 폴더 전체가
  지워질 수 있었습니다. 이제 폴더에 이 앱의 파일만 있을 때만 폴더째 지우고, 아니면 앱
  파일만 지웁니다. 남은 프로세스를 닫을 때도 폴더 경로 대신 이 앱 스크립트의 전체 경로로
  찾아, 다른 Python 프로그램을 닫지 않습니다.
- **보안: 진단 기록에 페이지 글자가 남던 문제**: Codex를 못 읽었을 때 `error.log`에 페이지
  앞부분 글자를 적었는데, 계정 이름이나 이메일이 들어갈 수 있었습니다. 페이지 주소와 제목만
  남깁니다.
- Save widget settings with the existing atomic JSON writer so an interrupted
  save keeps the previous complete settings file.
- Correct the documented UDP commands (now `show`, `autoshow`, `menu` and `exit`).

### English

#### Changed
- **Right-clicking a badge opens the full menu**, the same one as the widget and
  the notification icon, so view mode, display mode, language, sync fixes and
  Close are reachable from the badges even in badges-only mode.
  `Reset badge positions` is in that menu (shown only while badges are in use).
- **Installing no longer needs Python up front**: when neither uv nor Python is
  found, `install.cmd` installs Python 3.12 for the current user and carries on.
  It tries `winget` first and otherwise downloads the official python.org
  installer (the ARM build on ARM PCs). It also finds an installed Python that
  is not on PATH, and no longer mistakes the Microsoft Store `python` shortcut
  for a real interpreter.
- **The menu's `Uninstall` became `Quit`; uninstall from Windows `Installed apps`**:
  - `Close (back when an app opens)`: closes the widget; it comes back the next
    time Claude or ChatGPT opens.
  - `Quit (no auto-start)`: also stops the watcher, so nothing starts again, even
    after a restart, until the widget is opened from its desktop shortcut.
  - Installing registers the app under `Settings → Apps → Installed apps`
    (Control Panel → Programs), so it is removed like any other program, after a
    confirmation. That removes the shortcuts, settings, sign-ins, the program
    folder and the entry itself. `uninstall.cmd` runs the same uninstaller.
- Pin GitHub Actions to verified commit SHAs and test settings replacement and
  replacement failures using temporary files.

#### Fixed
- **The widget's right-click menu did not open (0.9.1)**: building its submenus
  (display mode, language, sync fixes) raised an error, so the whole menu, and
  with it recovery items such as `Re-sign in`, was unusable. A Windows test now
  opens the menu and invokes every item.
- The hidden reader browser now uses a normal window size (1280×900) instead of
  1×1 (it runs on an invisible desktop, so nothing shows on screen). When usage
  cannot be read, the page's address and title are written to `error.log`.
- **Codex limits could not be read (address change)**: the ChatGPT usage page is
  now split into `Overview` and `Analytics` tabs, and the reader's address
  opened `Analytics` (`?tab=analytics`), which has no limits. It now opens
  `https://chatgpt.com/settings/usage?tab=overview` directly, and the widget uses
  that address when it opens the Codex website too.
- **Error text stayed in the previous language after switching languages**: the
  text is stored in the language the reader ran with, so it stayed until the
  next sync finished. Switching now shows `Syncing…` in the new language at once.
- **Claude kept showing `Official usage sync failed` ("Could not start the usage
  browser")**: a leftover dedicated Claude browser still held the profile, so
  every new launch handed off to it and exited. When a launch fails, and on
  `Restart reader browser`, browsers using that profile are closed and the
  reader launches again (your own Chrome is never touched). Looking for them
  takes seconds, so it is not done on every launch.
- **Old usage looked current**: a reader stopped by its time limit left the
  previous values in the cache, and the badges kept showing them without any
  sign that syncing had stopped. Numbers not refreshed for over 3 minutes are now
  drawn grey. The reader time limit went from 60 to 150 seconds (room for a page
  reload, a security check and a second attempt).
- **Security checks (Cloudflare) failed the sync or signed you out**: Claude took
  the check page for a sign-out and asked you to sign in again; Codex just
  failed. Such a check usually clears by itself within seconds, so the readers
  now wait 25 seconds more and then show `Security check needed`; press ↻ and
  pass it once in the window that opens.
- **After `Exit` the widget never came back when an app opened**: exiting also
  turned auto-start off. Closing now only closes the widget.
- **Security: other Windows accounts on the same PC could reach the reader
  browser**: its debug port listens on this PC only, but every account signed in
  to the PC can reach it. While another account is signed in, the browser is
  closed after every sync, so the port is open only during the few seconds a
  sync takes (on a PC used by one person it stays open as before).
- **ChatGPT could be taken as signed out by mistake**: while the usage page was
  still loading, the word `로그인` ("sign in") anywhere on it made the reader
  treat it as the sign-in page and drop the connection. Only leaving the
  settings page for the sign-in or home page counts as signed out now.
- **Security: a downloaded Python installer was run unchecked**: the python.org
  installer now runs only with a valid Python Software Foundation signature.
- **Codex usage showed an old, lower value**: the reader read the usage page the
  background browser already had open, and that page never updates its numbers
  by itself, so it kept showing the value from when the browser started (8%
  while 12% was used). The page is now reloaded on every sync. Claude is not
  affected: its reader presses the page's refresh button.
- **The Codex badge did not appear on the ChatGPT window at startup**: the
  ChatGPT app shows a window while it starts and then hides it, and the badge
  kept following that hidden window until a display-mode switch restarted the
  badge helper. While the followed window is off screen, the badge looks for the
  app window again every second.
- **In badges-only mode Codex usage was empty after start**: the widget reads
  Claude and then Codex, and each launch first looked for leftover browsers, so
  Codex, second in line, ran past the 60-second limit, and the next sync was two
  minutes away. That check now runs only after a failed launch, and a reader that
  fails is retried after 20 seconds (twice in a row at most).
- **Security: uninstall could delete a folder holding other files**: uninstall
  deleted the whole program folder, so app files dropped straight into a folder
  such as `Downloads` could take that folder with them. The folder is deleted
  only when it holds nothing but the app's files; otherwise only the app's files
  are removed. Leftover processes are found by the full paths of the app's
  scripts rather than the folder, so other Python programs are never closed.
- **Security: page text in the diagnostic log**: when Codex could not be read,
  `error.log` got the start of the page text, which can include the account name
  or e-mail address. Only the page's address and title are logged now.
- Save widget settings with the existing atomic JSON writer so an interrupted
  save keeps the previous complete settings file.
- Correct the documented UDP commands (now `show`, `autoshow`, `menu` and `exit`).

## [0.9.1] - 2026-10-27

### Fixed
- **Codex 앱이 켜진 걸 위젯이 못 알아채던 문제**: 위젯은 실행 파일 이름에 `chatgpt`가
  들어간 것만 Codex 앱으로 봤는데, Codex 데스크톱 앱은 `Codex.exe`입니다. 그래서 배지만
  모드에서 Codex가 동기화되지 않거나, 자동 보기가 Codex를 놓치거나, Codex 부분 더블클릭이
  앱으로 가지 않을 수 있었습니다. 이제 `Codex.exe`도 인식하고, 둘 다 켜져 있으면 Codex
  앱 → ChatGPT → ChatGPT Classic 순으로 고릅니다.
- **좁은 창에서 Claude 배지가 창 왼쪽 밖으로 밀려나던 문제**: 배지가 창 안에 머뭅니다.
- **한국어 모드에서 일부 오류가 영어로 나오던 문제**: 브라우저 연결 단계의 오류 7개가
  영어로만 적혀 있어, Codex 쪽에서는 그대로 위젯에 보였습니다. 이제 고른 언어로 나옵니다.
- **영어 배지의 초기화 시간 형식이 제각각이던 문제**: `in 2h 12m`처럼 한 형식으로 맞추고,
  `Resets Oct 24, 5:10 PM` 같은 날짜도 한국어처럼 남은 시간(`in 2d 2h`)으로 바꿉니다.

### Changed
- **설치에 pywin32가 필요 없습니다.** 바로가기를 Windows의 바로가기 인터페이스(IShellLinkW)를
  Python 표준 `ctypes`로 직접 불러 만들어, 이제 앱 전체가 Python 표준 라이브러리만 씁니다.
  pywin32 설치 단계와 그 오류가 사라졌고, 사용자·폴더 이름에 어떤 문자가 있어도 경로가
  깨지지 않습니다(새 Windows 테스트로 확인).
- 알림 아이콘 메뉴와 위젯 우클릭 메뉴를 메뉴 정의 하나로 만듭니다(겉모습·동작은 같음).
- Codex 리더가 Claude 리더의 동기화 흐름을 그대로 복사해 두던 것을 공유하도록 정리하고,
  자동 업데이트 시절의 재시작 처리·아무도 보내지 않는 제어 명령·Windows가 아닌 환경용 분기
  같은 쓰이지 않는 코드를 지웠습니다(동작은 같음).
- 설치 프로그램이 실제로 바로가기를 만드는지 Windows 자동 테스트로 확인합니다.
- Codex 리더의 `--self-test`를 정규 테스트(`tests/`)로 옮겼고, GitHub에 올릴 때마다
  Windows에서 테스트가 자동으로 돕니다.

### Removed
- **Codex `로컬 CLI 기록` 데이터 소스와 `Codex Spark 사용량도 표시` 토글**: Codex 사용량은
  이제 공식 페이지(브라우저)로만 읽습니다. 로컬 기록은 Codex CLI로 요청할 때만 갱신돼,
  Codex·ChatGPT 앱 위주로 쓰면 값이 멈춰 보였습니다. `codex_usage.py`, 메뉴의
  `Codex 데이터 소스`·Spark 항목, `오래된 기록` 표시가 함께 빠졌습니다. 예전 설정 파일의
  해당 값은 무시합니다.
- 0.1.0 이전 단독 위젯(Claude 전용·Codex 전용) 정리 기능과 `cleanup-legacy.cmd`.
- 갱신이 멈춘 `HISTORY.md`와 쓰지 않는 `assets/screenshot.svg`.

### English

#### Fixed
- **The widget did not notice the Codex app**: only executables with `chatgpt`
  in their name counted as the Codex app, but the Codex desktop app is
  `Codex.exe`. In badges-only mode Codex could go unsynced, the auto view could
  miss it, and double-clicking the Codex part might not open the app. `Codex.exe`
  is now recognised, and when both run the order is Codex app → ChatGPT →
  ChatGPT Classic.
- **On a narrow window the Claude badge was pushed off the window's left edge**:
  it now stays on the window.
- **Some errors appeared in English in Korean mode**: seven browser-connection
  errors existed only in English and showed up as-is for Codex. They now follow
  the chosen language.
- **English badges used mixed reset-time formats**: they now use one format,
  such as `in 2h 12m`, and dates like `Resets Oct 24, 5:10 PM` become time left
  (`in 2d 2h`), as in Korean.

#### Changed
- **Installing no longer needs pywin32.** Shortcuts are created by calling
  Windows' shell-link interface (IShellLinkW) directly with Python's standard
  `ctypes`, so the whole app now uses only the standard library. The pywin32
  step and its errors are gone, and paths survive any characters in user or
  folder names (checked by a new Windows test).
- The notification-icon menu and the widget's right-click menu are built from
  one menu definition (same look and behaviour).
- The Codex reader now shares the Claude reader's sync flow instead of a copy,
  and unused code was removed: restart handling from the auto-update days, a
  control command nothing sent, and non-Windows branches (no behaviour change).
- A Windows test checks that the installer really creates its shortcuts.
- The Codex reader's `--self-test` moved into the regular tests (`tests/`), which
  now run on Windows for every push to GitHub.

#### Removed
- **The Codex `Local CLI logs` data source and the `Also show Codex Spark usage`
  toggle**: Codex usage is now read from the official page (browser) only. The
  local logs update only for Codex CLI requests, so with the Codex/ChatGPT apps
  the values looked frozen. `codex_usage.py`, the `Codex data source` and Spark
  menu items and the `old record` marker went with it; those values in older
  settings files are ignored.
- The clean-up of the pre-0.1.0 standalone widgets (Claude-only, Codex-only) and
  `cleanup-legacy.cmd`.
- The no longer updated `HISTORY.md` and the unused `assets/screenshot.svg`.

## [0.9.0] - 2026-10-27

첫 공식 릴리스입니다. 아래는 0.8.x에서 바뀐 내용입니다.

### Added
- **표시 방식 선택 + 앱 제목 표시줄 사용량 배지**: 우클릭·알림 아이콘 메뉴의
  **`표시 방식`** 에서 셋 중 하나를 고릅니다.
  - **위젯만**: 예전처럼 떠 있는 위젯만.
  - **앱 제목 표시줄 배지만**: 위젯은 숨긴 채 Claude·Codex 앱 창의 배지로만 봅니다.
    앱이 켜질 때도, 알림 아이콘·바탕화면 바로가기·배지를 눌러도 위젯이 뜨지 않으며
    **`표시 방식`을 바꿀 때만** 다시 나옵니다. 동기화는 켜져 있는 앱만 합니다.
  - **위젯 + 제목 표시줄 배지** (기본): 둘 다.
- 배지는 Claude 앱·Codex(ChatGPT) 앱 창의 제목 표시줄에 앱 버튼을 가리지 않게 붙어
  (Claude는 앱 도구 모음 왼쪽, Codex는 –/□/× 버튼 왼쪽),
  한도별 **사용량 %, 얇은 막대, 초기화까지 남은 시간**을 보여줍니다. 색은 위젯과 같아요
  (75% 이상 주황, 90% 이상 빨강).
  - 앱 창에 "소유된" 창이라 **창을 옮기면 따라가고, 다른 창에 가려지면 같이 가려지며,
    최소화하면 숨습니다.**
  - Codex 공식 페이지의 날짜형 초기화 시각(`2026. 10. 24. 오후 5:10`)은 **남은 시간
    (`2일 2시간 후`)** 으로 바꿔 보여줍니다.
  - 배지를 드래그해 위치를 바꾸면 앱별로 기억하고(배율이 달라도 유지), 배지 우클릭 →
    `배지 위치 초기화`로 되돌립니다. 더블클릭하면 위젯이 열립니다(배지만 모드 제외).
  - 화면 배율(125%/150%)에서도 위치가 맞도록 배율을 인식하는 별도 보조 프로세스
    (`title_badges.py`)로 그리며, 위젯이 꺼지면 함께 종료됩니다. 위젯이 이미 저장한
    사용량 캐시만 읽고, 앱이나 쿠키·토큰은 건드리지 않습니다.

### Fixed
- **pywin32를 처음 설치할 때 `install.cmd`가 실패하던 문제**: pywin32를 설치한 직후 같은
  실행 안에서 `pywintypes`를 못 찾아 `pywin32 still could not be loaded` 오류가 났습니다.
  설치 직후 pywin32 경로를 바로 읽어 들여 한 번에 설치됩니다.
- **Claude 배지가 앱의 공유·폴더 버튼을 가리던 문제**: Claude 앱은 –/□/× 왼쪽에 자체
  도구 모음이 있어, 기본 위치를 그 도구 모음 왼쪽으로 옮겼습니다.
- **Codex 배지 글자가 오른쪽에서 잘리던 문제**: 한글이 없는 Segoe UI로 폭을 재서 한글이
  실제보다 좁게 계산됐습니다. 한국어에서는 맑은 고딕으로 재고 그립니다.
- **Codex 한도 이름·초기화 문구**: 페이지가 `주간 사용 한도6일 16시간 후 초기화됩니다`처럼
  한 줄로 붙여 보여 줄 때, 이름(`주간 한도`)과 시간을 나누고 `초기화됩니다`는 `초기화`로
  줄입니다. 뒤에 붙어 나오는 `37% 남음` 같은 문구도 잘라 냅니다. 배지의 남은 시간도 `6일 16시간 후 초기화`처럼 `초기화`로 끝납니다.
- **위젯을 꺼도 프로그램 폴더가 안 지워지던 문제(남은 원인)**: 시작 프로그램 감시자와
  위젯이 프로그램 폴더를 작업 폴더로 잡고 있었습니다. 이제 바로가기와 모든 프로세스가
  데이터 폴더(`%LOCALAPPDATA%\ClaudeCodexUsage`)에서 돌아, 종료 후 바로 폴더를 지울 수 있습니다.
- **제거 후 찌꺼기가 남던 문제**: `uninstall.cmd`/메뉴의 제거가 위젯·감시자가 실제로 끝날
  때까지 기다리고, 남은 전용 Chrome과 이 앱의 Python 프로세스를 닫은 뒤 지웁니다. 잠겨
  있던 파일은 백그라운드에서 최대 1분간 다시 지우고, 옛 단독 위젯의 바로가기도 함께 지웁니다.
- **글자가 어둡게 보이던 문제**: 위젯·배지의 이름(세션·주간)과 초기화 시간을 회색 대신
  흰색으로, 사용량 %의 파란색을 조금 더 진하게 바꿨습니다.
- **영어 모드에서 일부만 영어로 나오던 문제**: Claude·ChatGPT 페이지에서 읽어 온
  초기화 시간(`2시간 후 재설정`, `(월) 오전 8:00`, `2026. 10. 24. 오후 5:10 초기화`)과
  Codex 한도 이름(`주간 사용 한도`)을 위젯에서 고른 언어로 바꿔 보여 줍니다. 리더의 오류
  문구, 제거 완료 안내, 설치 메시지도 언어를 따릅니다.
- **`앱 제목 표시줄 배지만`에서 위젯이 다시 뜨던 문제**: 알림 아이콘 클릭, 바탕화면
  바로가기, 배지 더블클릭으로는 위젯이 뜨지 않습니다. 위젯은 `표시 방식`을 바꿀 때만
  다시 나타납니다. 이 모드에서는 알림 아이콘 메뉴의 위젯 전용 항목(항상 위, 위치 초기화,
  표시/숨기기, 좌우 전환)이 회색으로 잠기고, 배지 메뉴의 `위젯 열기`도 사라집니다.
- **배지만 모드에서 `Claude만 보기`·`Codex만 보기`를 고를 수 없던 문제**: 보기 모드가
  배지에도 적용돼, 고른 앱의 배지만 보여 주고 그 앱만 동기화합니다.
- **배지 글자 잘림**: 배지 높이를 고정값 대신 글꼴의 실제 줄 높이로 계산해
  아래 초기화 시간 줄이 잘리지 않습니다. 글자를 조금 줄여 제목 표시줄(약 40px)
  안에 들어갑니다.
- **초기화 시간 정리**: 페이지 문구가 길어도 `1시간 20분 후`, `(월) 오전 8:00`
  같은 시간 부분만 보여 줍니다. `(월요일)`은 `(월)`로 줄입니다.
- **Codex 배지 이름**: `5시간 한도`는 `세션`으로, 이름이 `한도`뿐이면 초기화
  문구를 보고 `주간`을 붙입니다.
- **프로그램을 꺼도 폴더가 지워지지 않던 문제**: Claude·Codex용 전용 Chrome이 프로그램
  폴더를 작업 폴더로 물고 떠 있어서, Windows가 그 폴더의 삭제·교체를 막았습니다. 게다가
  위젯을 끌 때 Claude용 Chrome만 닫고 Codex용 Chrome은 남겨 두었습니다.
  - 전용 Chrome을 앱 데이터 폴더(`%LOCALAPPDATA%\ClaudePet`)에서 띄워 프로그램 폴더를
    잡지 않게 했습니다. 제목 표시줄 배지 프로세스도 같습니다.
  - 위젯을 끌 때 **Claude용·Codex용 Chrome을 둘 다** 닫습니다.

### English

First official release. Changes since 0.8.x:

#### Added
- **Display mode choice and usage badges on the app title bars**: pick one of
  three in **`Display`** in the right-click and notification-icon menus.
  - **Widget only**: the floating widget, as before.
  - **Title-bar badges only**: the widget stays hidden and usage shows only as
    badges on the Claude and Codex app windows. The widget does not appear when
    an app starts, nor from the notification icon, desktop shortcut or a badge;
    it comes back **only when `Display` is changed**. Only running apps are
    synced.
  - **Widget + title-bar badges** (default): both.
- Badges sit on the title bars of the Claude and Codex (ChatGPT) app windows
  without covering the app's buttons (left of Claude's toolbar; left of the
  –/□/× buttons for Codex) and show each limit's **usage %, a thin bar and the
  time until reset**, in the widget's colours (orange from 75%, red from 90%).
  - They are windows "owned" by the app window, so **they follow it when it
    moves, are covered with it, and hide when it is minimised.**
  - Date-style reset times from the Codex page (`2026. 10. 24. 오후 5:10`) are
    shown as **time left** (`2일 2시간 후`).
  - Dragging a badge remembers its place per app (even across display scales);
    right-click → `Reset badge position` puts it back. Double-clicking opens the
    widget (except in badges-only mode).
  - They are drawn by a separate DPI-aware helper process (`title_badges.py`) so
    they line up at 125%/150% scaling, and it exits with the widget. It reads
    only the usage cache the widget already saved and never touches the apps,
    cookies or tokens.

#### Fixed
- **`install.cmd` failed on a first pywin32 install**: right after installing
  pywin32, the same run could not find `pywintypes` ("pywin32 still could not be
  loaded"). The pywin32 paths are now loaded right after install, so it works in
  one go.
- **The Claude badge covered the app's share and folder buttons**: the Claude app
  has its own toolbar left of –/□/×, so the default spot moved left of it.
- **Codex badge text was cut off on the right**: widths were measured with Segoe
  UI, which has no Hangul, so Korean came out narrower than drawn. Korean is now
  measured and drawn with Malgun Gothic.
- **Codex limit names and reset text**: when the page runs them together, as in
  `주간 사용 한도6일 16시간 후 초기화됩니다`, the name (`주간 한도`) and the time are
  split and `초기화됩니다` is shortened to `초기화`; trailing text such as `37% 남음` is
  dropped. Badge time-left text also ends in `초기화`.
- **The program folder could not be deleted after closing the widget (remaining
  cause)**: the Startup watcher and the widget used the program folder as their
  working folder. Shortcuts and every process now run from the data folder
  (`%LOCALAPPDATA%\ClaudeCodexUsage`), so the folder can be deleted right after
  exiting.
- **Uninstall left things behind**: `uninstall.cmd` and the menu's uninstall now
  wait until the widget and watcher have really exited, close leftover dedicated
  Chrome and this app's Python processes, and then delete. Locked files are
  retried in the background for up to a minute, and old standalone-widget
  shortcuts are removed too.
- **Text looked dim**: names (session, weekly) and reset times in the widget and
  badges are white instead of grey, and the blue for usage % is a little deeper.
- **English mode was only partly English**: reset times read from the Claude and
  ChatGPT pages (`2시간 후 재설정`, `(월) 오전 8:00`, `2026. 10. 24. 오후 5:10 초기화`) and
  Codex limit names (`주간 사용 한도`) are shown in the widget's language. Reader
  errors, the uninstall notice and installer messages follow the language too.
- **The widget reappeared in `Title-bar badges only`**: the notification icon,
  desktop shortcut and badge double-click no longer show it; it reappears only
  when `Display` changes. In this mode the widget-only items of the
  notification-icon menu (always on top, reset position, show/hide, arrows view)
  are greyed out, and the badge menu's `Open widget` is gone.
- **`Claude only` / `Codex only` could not be chosen in badges-only mode**: the
  view mode now applies to badges too, showing and syncing only the chosen app.
- **Badge text clipping**: the badge height comes from the fonts' real line
  heights, so the bottom reset line is not cut off, and the text is a little
  smaller to fit the ~40 px title bar.
- **Reset-time clean-up**: however long the page's text, only the time part such
  as `1시간 20분 후` or `(월) 오전 8:00` is shown; `(월요일)` becomes `(월)`.
- **Codex badge names**: `5시간 한도` becomes `Session`, and a bare `한도` gets
  `Weekly` when the reset text says so.
- **The folder could not be deleted after closing the program**: the dedicated
  Claude and Codex Chrome kept the program folder as their working folder, so
  Windows blocked deleting or replacing it, and closing the widget closed only
  Claude's Chrome, not Codex's.
  - Dedicated Chrome now starts in the app data folder
    (`%LOCALAPPDATA%\ClaudePet`) so it never holds the program folder; the
    title-bar badge process does the same.
  - Closing the widget closes **both** dedicated Chrome instances.

## [0.8.4] - 2026-10-05

### Fixed
- **옮겨 둔 위젯이 작업표시줄 시계 위로 되돌아가던 문제**: 위치를 잡을 때 항상
  **주 모니터** 작업 영역으로 범위를 제한해서, 다른 모니터로 옮겨도 동기화·다시
  그리기 때마다 주 모니터로 끌려왔습니다. 또 옮긴 위치가 저장되지 않아 다시 켜질
  때마다 기본 위치로 돌아갔습니다.
  - 이제 **위젯이 놓인 모니터** 기준으로만 범위를 제한해, 보조 모니터에 둬도 그대로
    있습니다.
  - 드래그로 옮긴 위치를 `settings.json`에 저장해 **재시작·재부팅 후에도 유지**합니다.
  - 그 모니터가 분리되면 주 모니터의 기본 위치로 돌아옵니다.

### Added
- 우클릭·알림 아이콘 메뉴에 **`위치 초기화 (시계 위로)`** 추가 — 기본 위치로 복귀.

### English

#### Fixed
- **A moved widget jumped back above the taskbar clock**: placement was always
  limited to the **primary monitor's** work area, so on another monitor every
  sync or redraw pulled it back, and the moved position was not saved, so each
  start returned to the default place.
  - Placement is now limited to **the monitor the widget is on**, so it stays on
    a secondary monitor.
  - A dragged position is saved in `settings.json` and **kept across restarts
    and reboots**.
  - If that monitor is disconnected, the widget returns to the default place on
    the primary monitor.

#### Added
- **`Reset position`** in the right-click and notification-icon menus, back to
  the default place.

## [0.8.3] - 2026-09-29

### Fixed
- **읽기 전용/OneDrive 폴더에 설치해도 동작**: 결과 캐시(`latest.json`,
  `codex_latest.json`)와 `error.log`를 **프로그램 폴더 대신 `%LOCALAPPDATA%\
  ClaudeCodexUsage`** 에 쓰도록 변경. 이전에는 프로그램 폴더에 써서, OneDrive로
  동기화되는 `문서` 폴더 등에 두면 `FileNotFoundError`로 동기화가 실패했습니다. 이제
  **문서함(OneDrive)에 둬도 정상 동작**합니다.

### English

#### Fixed
- **Works when installed in a read-only or OneDrive folder**: the result caches
  (`latest.json`, `codex_latest.json`) and `error.log` are written to
  **`%LOCALAPPDATA%\ClaudeCodexUsage` instead of the program folder**. Writing to
  the program folder made syncing fail with `FileNotFoundError` in a folder such
  as an OneDrive-synced `Documents`; **such folders work now**.

## [0.8.2] - 2026-09-29

### Changed
- **메뉴 정리**: `제거 (Uninstall)`를 `표시 / 숨기기` **위로** 이동.
- **완전 제거 강화**: `제거`가 이제 바로가기·설정·로그인 데이터뿐 아니라 **프로그램
  폴더 자체까지 삭제**합니다(되돌릴 수 없음). 실행 중인 폴더는 자기 자신을 못 지우므로,
  종료 후 별도 프로세스가 잠금이 풀리면 삭제합니다. OneDrive의 한글 폴더 같은
  비ASCII 경로도 안전하게 지워지도록 Python으로 처리합니다.

### English

#### Changed
- **Menu order**: `Uninstall` moved **above** `Show / Hide`.
- **Thorough uninstall**: `Uninstall` now deletes **the program folder itself**
  as well as shortcuts, settings and sign-in data (cannot be undone). A running
  folder cannot delete itself, so a separate process deletes it once the lock is
  released after exit. Deletion is done in Python so non-ASCII paths, such as a
  Korean OneDrive folder, are removed safely.

## [0.8.1] - 2026-09-29

### Added
- **위젯에서 동기화 문제 해결**: 우클릭·알림 아이콘 메뉴에 **`동기화 문제 해결`**
  하위 메뉴 추가 — cmd 없이 위젯에서 바로 복구합니다.
  - **다시 시도**: 강제 재동기화.
  - **리더 브라우저 재시작**: 리더 브라우저를 닫고(`--close`) 다시 동기화. 숨긴
    브라우저가 스로틀·Cloudflare로 멈춰 `동기화 실패 (timed out)`이 뜰 때의 핵심
    해결책.
  - **다시 로그인**: 로그인(브라우저) 창을 다시 엽니다(세션 만료 시).
  - 현재 화면에 보이는 소스(Claude/Codex, 스택뷰면 둘 다)에 적용됩니다.

### English

#### Added
- **Fix sync issues from the widget**: a **`Fix sync issues`** submenu in the
  right-click and notification-icon menus repairs things without cmd.
  - **Retry now**: force a resync.
  - **Restart reader browser**: close the reader browser (`--close`) and sync
    again; the main fix when a hidden browser stalls on throttling or Cloudflare
    and shows `Sync failed (timed out)`.
  - **Re-sign in**: open the sign-in (browser) window again (expired session).
  - These apply to the sources on screen (Claude/Codex, both in the stacked view).

## [0.8.0] - 2026-09-15

### Added
- **위젯에 버전 표시**: 제목(USAGE) 아래 작게 현재 버전(`v0.8.0`)을 표시합니다.
- **제거(Uninstall) 메뉴**: 우클릭·알림 아이콘 메뉴에 **`제거 (Uninstall)`** 추가.
  확인 후 위젯·감시자를 종료하고 전용 브라우저를 닫은 뒤 **바로가기·설정·로그인
  데이터를 모두 제거**합니다(프로그램 폴더 자체는 남김). `uninstall.cmd`로도 실행
  가능합니다.
- **Codex 데이터 소스 선택 (기본: 공식 페이지/브라우저)**: 우클릭·알림 아이콘
  메뉴에 **`Codex 데이터 소스`** 하위 메뉴 추가 — `공식 페이지 (브라우저)` /
  `로컬 CLI 기록`.
  - **공식 페이지(기본):** Claude처럼 전용 브라우저로 ChatGPT usage 페이지를 읽어
    **ChatGPT 앱·웹 사용량까지 포함된 진짜 한도**를 보여줍니다(예: 주간 68% 사용).
    로컬 CLI 기록만 읽던 방식은 앱/웹 사용분을 못 잡아 값이 낡는 한계가 있었는데,
    이를 해결합니다. 처음 한 번 ChatGPT 로그인이 필요하며(전용 프로필, Claude와 분리),
    쿠키·토큰은 읽지 않고 화면에 렌더된 값만 읽습니다. 페이지가 `남음`으로 표시하는
    값은 위젯에선 **사용량**으로 변환해 일관되게 보여줍니다.
  - **로컬 CLI 기록:** 로그인 없이 `~/.codex` 로그만 읽는 기존 방식. Spark 토글도
    이 모드에서 동작합니다.
- **Codex Spark 사용량 표시 토글**: 우클릭·알림 아이콘 메뉴에 **`Codex Spark
  사용량도 표시`** 추가 (기본 **꺼짐**).
  - **꺼짐(기본):** 일반 codex 한도(현재 세션·주간)만 표시.
  - **켜짐:** 실제로 사용 중인 버킷을 모두 표시 — 일반만 쓰면 일반, Spark만 쓰면
    Spark, **둘 다 쓰면 둘 다** (모델 버킷은 `현재 세션 · Spark`처럼 라벨에 모델
    태그가 붙어 계정 전체 한도와 구분됩니다).
  - "사용 중"은 각 버킷의 최신 기록이 해당 세션 창(기본 5시간) 안에 있는지로 판단.

### Fixed
- **Codex 사용량이 갱신되지 않던 문제**: `0.7.0`에서 "모델별 버킷 제외" 필터가
  일반(`codex`) 버킷만 표시하도록 했는데, GPT-5.3-Codex-Spark처럼 **모델별 한도만
  실제로 쓰는 경우** 일반 버킷이 갱신되지 않아(예: 25시간 전 값) 위젯이 낡은 값에
  멈춰 "오래된 기록"으로 표시됐습니다. 이제 Spark가 꺼져 있어도 **일반 버킷이 오래됐고
  Spark만 쓰는 중이면 Spark를 자동으로 표시**해, 실제 사용 중인 한도가 항상 최신으로
  보이고 멈춘 것처럼 보이지 않습니다.
- Claude "공식 사용량 동기화 실패 (timed out)" when idle: the reader reloaded the
  usage page on every sync, and in the hidden window that reload could re-trigger
  Cloudflare's check and hang. It now reuses an already-loaded page (refreshing in
  place) instead of reloading, and retries the sync once so a cold first load can
  self-recover.

### English

#### Added
- **Version in the widget**: the current version (`v0.8.0`) appears in small type
  under the title (USAGE).
- **Uninstall menu item**: **`Uninstall`** in the right-click and
  notification-icon menus. After confirmation it stops the widget and watcher,
  closes the dedicated browsers and **removes the shortcuts, settings and sign-in
  data** (the program folder itself stays). `uninstall.cmd` does the same.
- **Codex data source choice (default: official page / browser)**: a
  **`Codex data source`** submenu with `Official page (browser)` and
  `Local CLI logs`.
  - **Official page (default):** like Claude, a dedicated browser reads the
    ChatGPT usage page, showing **the real limits including ChatGPT app and web
    usage** (e.g. 68% of the week used). Reading only local CLI logs missed app
    and web usage, so values went stale; this fixes that. A one-time ChatGPT
    sign-in is needed (separate profile from Claude); cookies and tokens are not
    read, only the rendered values. Values the page shows as `remaining` are
    converted to **usage** so the widget is consistent.
  - **Local CLI logs:** the previous way, reading only `~/.codex` logs with no
    sign-in. The Spark toggle works in this mode.
- **Codex Spark usage toggle**: **`Also show Codex Spark usage`** in the
  right-click and notification-icon menus (default **off**).
  - **Off (default):** only the general Codex limits (current session, weekly).
  - **On:** every bucket in use: general, Spark, or **both** (model buckets carry
    a model tag, as in `Current session · Spark`, to tell them from the account
    limits).
  - "In use" means the bucket's latest record falls within its session window
    (5 hours by default).

#### Fixed
- **Codex usage did not update**: in `0.7.0` the "exclude per-model buckets"
  filter showed only the general (`codex`) bucket, so when **only a model-specific
  limit is really used**, as with GPT-5.3-Codex-Spark, the general bucket went
  stale (e.g. 25 hours old) and the widget froze on it as an "old record". Now,
  even with Spark off, **Spark is shown automatically when the general bucket is
  stale and only Spark is in use**, so the limit actually in use is always
  current.
- Claude "Official usage sync failed (timed out)" when idle: the reader reloaded
  the usage page on every sync, and in the hidden window that reload could
  re-trigger Cloudflare's check and hang. It now reuses an already-loaded page
  (refreshing in place) instead of reloading, and retries the sync once so a
  cold first load can self-recover.

## [0.7.0] - 2026-09-14

### Fixed
- Fix Claude "공식 사용량 동기화 실패 (timed out)": the off-screen reader window was
  throttled by Chrome (background/occluded renderer), stalling the Claude SPA and
  its Cloudflare check so CDP calls timed out. Add anti-throttle launch flags
  (`--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows`,
  `--disable-renderer-backgrounding`) and raise the CDP socket timeout 10s → 25s
  for cold loads.
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

### English

#### Fixed
- **The widget did not show automatically when an app started**: the watcher was
  never updated.
  - `install.cmd` (install.py) now **stops this app's running widget and watcher
    first** and then starts fresh ones. Before, the old watcher held its port
    (47672) exclusively (EXCLUSIVEADDRUSE), so the new one failed to bind and
    died, and re-running `install.cmd` left the old code running.
  - The watcher retries binding its port for a few seconds at start, so it gets
    past the short gap while a reinstall frees the port.
  - Claude/ChatGPT desktop app detection uses **substring matching**
    (`claude`/`chatgpt`) instead of the exact exe name (`chatgpt.exe`), so it
    works when a build names its executable differently (as double-click app
    opening already did).

## [0.6.1] - 2026-09-02

### Fixed
- **반복 로그인 회귀 수정**: 0.5.0에서 동기화가 끝날 때마다 백그라운드 브라우저를
  종료(`close_browser`)하도록 한 변경이, 매 동기화마다 브라우저를 새로 띄우게 만들어
  Claude 로그인 세션이 유지되지 않았습니다(Claude가 인증 토큰을 갱신하는데, 종료 시
  갱신분이 유실됨). 그 결과 로그인해도 계속 "로그인 필요"가 뜨고 새 브라우저 창이
  열렸습니다. 이제 숨겨진 브라우저를 동기화 사이에 **계속 유지**하고 위젯 종료 시에만
  닫습니다. 디버그 포트는 `--remote-allow-origins=http://localhost` origin 제한으로
  이미 보호되므로 보안 저하는 없습니다.

### English

#### Fixed
- **Repeated sign-in regression**: the 0.5.0 change that closed the background
  browser after every sync (`close_browser`) made each sync launch a new one, so
  the Claude session was not kept (Claude refreshes its auth token, and the
  refresh was lost on close). Signing in still showed "sign-in needed" and new
  browser windows opened. The hidden browser is now **kept running** between
  syncs and closed only when the widget exits. The debug port is already
  protected by the `--remote-allow-origins=http://localhost` origin restriction,
  so security is not reduced.

## [0.6.0] - 2026-09-02

### Added
- **한국어 / 영어 전환**: 우클릭(창 아무 곳) 및 알림 아이콘 메뉴에 **`언어
  (Language)`** 하위 메뉴 추가 — `한국어` / `English` 선택. 보기 모드·항상 위·
  표시/숨김·종료 등 메뉴 문구, 업데이트 배지, 상태 문구가 모두 번역됩니다. 전환하면
  리더 스크립트(`usage.py`·`codex_usage.py`)가 `--lang`으로 라벨(현재 세션/모든 모델,
  주간 한도 등)과 재설정 문구를 새 언어로 다시 생성합니다. 선택은 `settings.json`의
  `lang`에 저장됩니다.
  - Claude의 재설정 문구는 Claude 페이지에서 읽어 오므로 Claude 계정 언어를 따릅니다.

### English

#### Added
- **Korean / English switch**: a **`Language`** submenu in the right-click
  (anywhere on the window) and notification-icon menus: `한국어` / `English`.
  Menu text (view modes, always on top, show/hide, exit…), the update badge and
  status text are all translated. Switching makes the reader scripts
  (`usage.py`, `codex_usage.py`) regenerate their labels (current session / all
  models, weekly limit…) and reset text in the new language via `--lang`. The
  choice is saved as `lang` in `settings.json`.
  - Claude's reset text is read from the Claude page, so it follows the Claude
    account's language.

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

### English

#### Security
- **Auto-update removed in favour of notifications**: the widget no longer
  downloads and runs code on its own. At start it only checks read-only
  (`git fetch`, no checkout), and when a newer version exists a red
  **`● Update available`** badge appears in the header. Clicking it opens the
  GitHub repository so you review and install it yourself (`git pull`, then
  `install.cmd`). The check runs only when `origin` is the official HTTPS
  repository and can be turned off with `CLAUDE_CODEX_NO_UPDATE=1` or a
  `.noupdate` file. With no silent code execution, a compromised repository
  cannot run arbitrary code.
- **Browser debug port origin restriction**: `--remote-allow-origins=*` →
  `http://localhost`, blocking malicious web pages from attaching to the DevTools
  port (DNS rebinding and the like). The port stays loopback-only as before, and
  the browser is closed after a sync so no port is left open.
- **Codex log parsing hardening**: abnormally long rollout lines are skipped
  before parsing (`MAX_LINE_CHARS`), so a corrupt or malicious file cannot
  exhaust memory.
- Added the security policy **`SECURITY.md`** and a security section in the
  README.

#### Notes
- The control ports (UDP 47671/47672) stay loopback-only, handled with a 64-byte
  cap and a fixed command allowlist. Every external process is started without a
  shell, as an argv list, and app launch targets (AUMIDs, URLs) are hard-coded
  constants.

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

### English

#### Added
- **Auto view mode** (new default): the view follows the running apps. Only
  Claude open → Claude usage only; only Codex (ChatGPT) → Codex only; both →
  both (stacked). **Closing one leaves the other; closing both hides the window,
  and opening an app again brings it back.** A fixed mode can still be chosen
  from the tray, `▾` or right-click menu.
- **Right-click anywhere on the window** shows the same menu as the tray
  (taskbar) right-click (view mode · always on top · show/hide · exit).

#### Changed
- The background watcher shows the widget when the Claude or ChatGPT desktop app
  starts. The watcher is a separate process, so **re-run `install.cmd`** or
  reboot to replace it with the latest one.

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

### English

#### Added
- Double-click **always opens the app**: a running Claude/ChatGPT desktop app is
  focused, and a closed one is **launched directly** by AUMID
  (`shell:AppsFolder`). (Both are Microsoft Store apps whose exe cannot be run
  directly, hence the AUMID.) The website is used only when the app is not
  installed.
- **Show the widget when an app starts**: a background watcher shows the widget
  when it sees the Claude/ChatGPT desktop app start. (It only checks the process
  list every 2 seconds, so CPU and memory cost is negligible.)
- **`cleanup-legacy.cmd`** to remove leftovers of the old standalone widgets
  (claude-usage, codex-usage). Installing also removes their old Startup and
  desktop shortcuts so old versions no longer start at boot.

## [0.2.0] - 2026-08-31

### Added
- 트레이(작업표시줄 알림) 우클릭 메뉴에 **"항상 위 (Always on top)"** 토글 추가.
  끄면 일반 창처럼 다른 창 뒤로 내려갈 수 있고, 설정은 저장됩니다.

### Changed
- Codex 쪽 더블클릭이 사용량 페이지 대신 **실행 중인 ChatGPT 앱**을 엽니다.
  ChatGPT와 ChatGPT Classic이 모두 켜져 있으면 ChatGPT를 우선하며, 둘 다 실행
  중이 아니면 사용량 페이지로 폴백합니다. (Claude 쪽은 설치돼 있으면 Claude 앱,
  없으면 claude.ai — 기존과 동일)

### English

#### Added
- An **"Always on top"** toggle in the tray (taskbar notification) right-click
  menu. Off, the widget can go behind other windows like a normal window; the
  setting is saved.

#### Changed
- Double-clicking the Codex side opens the **running ChatGPT app** instead of the
  usage page. With both ChatGPT and ChatGPT Classic running, ChatGPT wins; with
  neither running it falls back to the usage page. (The Claude side opens the
  Claude app if installed, otherwise claude.ai, as before.)

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

### English

First version: `claude-usage` and `codex-usage` combined into one widget.

#### Added
- **Claude and Codex usage together** in one widget.
- Four view modes (default **Both**): both stacked / both with left-right arrows
  / Claude only / Codex only. Picked with the `▾` button between `↻` and `×` or
  the tray right-click; the choice is saved.
- `usage.py`: a reader for Claude's official Usage page in a dedicated browser.
- `codex_usage.py`: a local reader of the rate-limit snapshots the Codex CLI
  leaves in `~/.codex/sessions` (no browser or sign-in, `--self-test` supported).
- Double-click opens the matching app for the side clicked (Claude app / Codex
  usage page).
- A translucent window (about 85% opacity) that keeps its bottom edge in place
  when its height changes after being moved.

[0.9.3]: https://github.com/minsk8775/Claude-Codex-usage/releases/tag/v0.9.3
[0.9.2]: https://github.com/minsk8775/Claude-Codex-usage/releases/tag/v0.9.2
[0.9.1]: https://github.com/minsk8775/Claude-Codex-usage/releases/tag/v0.9.1
[0.9.0]: https://github.com/minsk8775/Claude-Codex-usage/releases/tag/v0.9.0
