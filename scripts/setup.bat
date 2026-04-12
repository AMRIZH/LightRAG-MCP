@echo off
setlocal EnableExtensions

echo [1/4] Creating virtual environment if missing...
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if errorlevel 1 (
    echo Failed to create .venv
    exit /b 1
  )
)

echo [2/4] Upgrading pip tooling...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
  echo pip upgrade failed
  exit /b 1
)

echo [3/4] Installing LightRAG and helper packages...
".venv\Scripts\python.exe" -m pip install "lightrag-hku[api]" pypdf requests
if errorlevel 1 (
  echo Package installation failed
  exit /b 1
)

echo [4/4] Creating data folders...
if not exist "data\inputs" mkdir "data\inputs"
if not exist "data\metadata" mkdir "data\metadata"
if not exist "data\inputs_prepared" mkdir "data\inputs_prepared"
if not exist "data\rag_storage" mkdir "data\rag_storage"
if not exist "data\tiktoken" mkdir "data\tiktoken"
if not exist "logs" mkdir "logs"

echo.
echo Setup finished.
if not exist ".env.local" (
  echo NOTE: .env.local is missing. Add your API keys before start-server.
)
