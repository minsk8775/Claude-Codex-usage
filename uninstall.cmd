@echo off
set "CLAUDE_USAGE_PYTHONW_FILE=%LOCALAPPDATA%\ClaudeCodexUsage\pythonw.path"
if not exist "%CLAUDE_USAGE_PYTHONW_FILE%" (
  echo Claude Codex Usage runtime information was not found.
  pause
  exit /b 1
)
set /p CLAUDE_USAGE_PYTHONW=<"%CLAUDE_USAGE_PYTHONW_FILE%"
start "" "%CLAUDE_USAGE_PYTHONW%" "%~dp0claude_usage.pyw" --uninstall
