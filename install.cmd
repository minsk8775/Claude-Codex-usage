@echo off
cd /d "%~dp0"

rem Prefer uv when available: it prepares pywin32 in an isolated environment.
where uv.exe >nul 2>nul
if not errorlevel 1 (
  uv run --isolated --with pywin32 python install.py
  if errorlevel 1 pause
  exit /b
)

rem uv is optional. Fall back to a plain Python interpreter.
where python.exe >nul 2>nul
if not errorlevel 1 (
  python install.py
  if errorlevel 1 pause
  exit /b
)

rem Try the Python launcher as a last resort.
where py.exe >nul 2>nul
if not errorlevel 1 (
  py install.py
  if errorlevel 1 pause
  exit /b
)

echo Neither uv nor Python was found.
echo Install uv (https://docs.astral.sh/uv/) or Python (https://www.python.org/), then run install.cmd again.
pause
exit /b 1
