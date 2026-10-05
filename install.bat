@echo off
setlocal
cd /d "%~dp0"
echo === Long Haul installer ===

set PY=
where py >nul 2>nul
if %errorlevel%==0 set PY=py -3
if "%PY%"=="" (
  where python >nul 2>nul
  if %errorlevel%==0 set PY=python
)
if "%PY%"=="" goto nopython

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto nopython

if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail

if not exist user mkdir user
echo Fetching live market data...
set PYTHONPATH=%~dp0src
.venv\Scripts\python -m irasim.live
echo.
echo Install complete. Starting Long Haul...
call run.bat --no-update
exit /b 0

:nopython
echo Python 3.11 or newer is required.
echo Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run this again.
pause
exit /b 1

:fail
echo Install failed. See the messages above.
pause
exit /b 1
