@echo off
setlocal
cd /d "%~dp0"
echo === IRA Review installer ===
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" || (
  echo Python 3.11 or newer is required. Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) and re-run.
  pause & exit /b 1
)
if not exist .venv ( %PY% -m venv .venv || (echo Could not create virtual environment & pause & exit /b 1) )
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt || (echo Dependency install failed & pause & exit /b 1)
if not exist user mkdir user
echo Fetching live market data...
set PYTHONPATH=%~dp0src
.venv\Scripts\python -m irasim.live
echo.
echo Done. Start the app with run.bat
pause
