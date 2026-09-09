@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Python environment not found. Run install.ps1 first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe src\app.py
