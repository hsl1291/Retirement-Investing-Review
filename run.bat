@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run install.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python run.py %*
if errorlevel 1 (
  echo.
  echo Long Haul stopped with an error. See the messages above.
  pause
)
