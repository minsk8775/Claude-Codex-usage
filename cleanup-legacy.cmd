@echo off
rem Stop and unregister older standalone Claude/Codex usage widgets so they no
rem longer open on boot. Keeps this combined app and everyone's saved settings.
cd /d "%~dp0"

where python.exe >nul 2>nul
if not errorlevel 1 (
  python install.py --cleanup-only
  pause
  exit /b
)

where py.exe >nul 2>nul
if not errorlevel 1 (
  py install.py --cleanup-only
  pause
  exit /b
)

echo Python was not found.
pause
exit /b 1
