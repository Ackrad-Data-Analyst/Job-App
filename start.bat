@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 start.py
) else (
  python start.py
)
if errorlevel 1 (
  echo Install Python 3.12 or newer and Node.js 24 LTS if needed.
  echo Python: https://www.python.org/downloads/
  echo Node.js: https://nodejs.org/
  pause
)
