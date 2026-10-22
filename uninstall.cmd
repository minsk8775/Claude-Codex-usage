@echo off
rem Run the uninstaller outside this folder so it can delete the folder itself.
cd /d "%TEMP%"
set "CLAUDE_USAGE_SCRIPT=%~dp0claude_usage.pyw"
set "CLAUDE_USAGE_PYTHONW_FILE=%LOCALAPPDATA%\ClaudeCodexUsage\pythonw.path"

rem Prefer the Python recorded by install.cmd.
if exist "%CLAUDE_USAGE_PYTHONW_FILE%" (
  set /p CLAUDE_USAGE_PYTHONW=<"%CLAUDE_USAGE_PYTHONW_FILE%"
)
if defined CLAUDE_USAGE_PYTHONW if exist "%CLAUDE_USAGE_PYTHONW%" (
  start "" "%CLAUDE_USAGE_PYTHONW%" "%CLAUDE_USAGE_SCRIPT%" --uninstall
  exit /b
)

rem The record is missing (an interrupted install, or settings already
rem removed). The uninstaller needs only the standard library, so any Python works.
where pythonw.exe >nul 2>nul
if not errorlevel 1 (
  start "" pythonw.exe "%CLAUDE_USAGE_SCRIPT%" --uninstall
  exit /b
)
where pyw.exe >nul 2>nul
if not errorlevel 1 (
  start "" pyw.exe "%CLAUDE_USAGE_SCRIPT%" --uninstall
  exit /b
)
where uv.exe >nul 2>nul
if not errorlevel 1 (
  start "" uv.exe run --isolated python "%CLAUDE_USAGE_SCRIPT%" --uninstall
  exit /b
)

echo Python was not found, so Claude Codex Usage cannot be uninstalled automatically.
echo Install Python (https://www.python.org/) or uv, then run uninstall.cmd again.
pause
exit /b 1
