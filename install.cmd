@echo off
setlocal
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

rem A Python installed earlier but not on PATH (e.g. just installed).
call :find_python
if defined CLAUDE_USAGE_PY goto run_python

echo Python was not found. Installing Python 3.12 for this user...
where winget.exe >nul 2>nul
if not errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  call :find_python
)
if defined CLAUDE_USAGE_PY goto run_python

rem No winget, or it failed: use the official installer from python.org.
set "CLAUDE_USAGE_ARCH=amd64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "CLAUDE_USAGE_ARCH=arm64"
set "CLAUDE_USAGE_SETUP=%TEMP%\python-3.12.10-%CLAUDE_USAGE_ARCH%.exe"
echo Downloading Python 3.12 from python.org...
curl.exe -fL --retry 2 -o "%CLAUDE_USAGE_SETUP%" "https://www.python.org/ftp/python/3.12.10/python-3.12.10-%CLAUDE_USAGE_ARCH%.exe"
if not errorlevel 1 (
  echo Installing Python 3.12 for this user. This can take a minute...
  "%CLAUDE_USAGE_SETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_test=0
  del "%CLAUDE_USAGE_SETUP%" >nul 2>nul
  call :find_python
)
if defined CLAUDE_USAGE_PY goto run_python

echo.
echo Python could not be installed automatically.
echo Install Python from https://www.python.org/downloads/ , then run install.cmd again.
pause
exit /b 1

:run_python
"%CLAUDE_USAGE_PY%" install.py
if errorlevel 1 pause
exit /b

rem Sets CLAUDE_USAGE_PY to an installed python.exe that has Tk, if any.
:find_python
set "CLAUDE_USAGE_PY="
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
  if exist "%%~D\python.exe" (
    "%%~D\python.exe" -c "import tkinter" >nul 2>nul
    if not errorlevel 1 set "CLAUDE_USAGE_PY=%%~D\python.exe"
  )
)
exit /b 0
