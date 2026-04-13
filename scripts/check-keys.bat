@echo off
setlocal EnableExtensions

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found.
  echo Run scripts\setup.bat first.
  exit /b 1
)

".venv\Scripts\python.exe" "scripts\check_api_keys.py" %*
