@echo off
cd /d "%~dp0"

rem Prefer uv when available; plain Python works just as well.
where uv.exe >nul 2>nul
if not errorlevel 1 (
  uv run --isolated python install.py
  if errorlevel 1 pause
  exit /b
)

rem A real Python with Tk. (Windows' "python" shortcut that only opens the
rem Microsoft Store fails this check, so it is skipped.)
python -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
  python install.py
  if errorlevel 1 pause
  exit /b
)
py -c "import tkinter" >nul 2>nul
if not errorlevel 1 (
  py install.py
  if errorlevel 1 pause
  exit /b
)

rem No Python yet: install it for this user with winget (built into Windows 10/11).
set "CLAUDE_USAGE_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%CLAUDE_USAGE_PY%" (
  where winget.exe >nul 2>nul
  if errorlevel 1 goto no_python
  echo Python was not found. Installing Python 3.12 for this user with winget...
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
)
if exist "%CLAUDE_USAGE_PY%" (
  "%CLAUDE_USAGE_PY%" install.py
  if errorlevel 1 pause
  exit /b
)

:no_python
echo Python could not be found or installed automatically.
echo Install Python (https://www.python.org/) or uv (https://docs.astral.sh/uv/), then run install.cmd again.
pause
exit /b 1
