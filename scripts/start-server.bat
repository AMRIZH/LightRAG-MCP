@echo off
setlocal EnableExtensions

if not exist ".venv\Scripts\lightrag-server.exe" (
  echo LightRAG server binary not found.
  echo Run scripts\setup.bat first.
  exit /b 1
)

if not exist ".env" (
  echo .env not found.
  exit /b 1
)

if /I not "%LIGHTRAG_SKIP_KEYCHECK%"=="1" (
  if not exist "scripts\check_api_keys.py" (
    echo Required preflight script is missing: scripts\check_api_keys.py
    echo Restore the file or set LIGHTRAG_SKIP_KEYCHECK=1 to bypass.
    exit /b 1
  )

  echo Running provider key preflight...
  ".venv\Scripts\python.exe" "scripts\check_api_keys.py" --timeout 20
  if errorlevel 1 (
    echo Provider preflight failed. Update keys in .env or set LIGHTRAG_SKIP_KEYCHECK=1 to bypass.
    exit /b 1
  )
)

echo Starting LightRAG server at http://127.0.0.1:9621
".venv\Scripts\python.exe" "scripts\run_server.py" %*
