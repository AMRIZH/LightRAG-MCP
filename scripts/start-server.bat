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

if not exist ".env.local" (
  echo .env.local not found.
  echo Add local API keys in .env.local.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (`findstr /R /V /C:"^[ ]*#" /C:"^[ ]*$" ".env.local"`) do (
  set "%%A=%%B"
)

if "%LLM_BINDING_API_KEY%"=="" (
  echo LLM_BINDING_API_KEY is missing in .env.local.
  exit /b 1
)

if /I "%LLM_BINDING_API_KEY%"=="REVOKE_AND_REPLACE" (
  echo LLM_BINDING_API_KEY is still a placeholder. Update .env.local first.
  exit /b 1
)

if "%EMBEDDING_BINDING_API_KEY%"=="" (
  echo EMBEDDING_BINDING_API_KEY is missing in .env.local.
  exit /b 1
)

if /I "%EMBEDDING_BINDING_API_KEY%"=="REVOKE_AND_REPLACE" (
  echo EMBEDDING_BINDING_API_KEY is still a placeholder. Update .env.local first.
  exit /b 1
)

echo Starting LightRAG server at http://127.0.0.1:9621
".venv\Scripts\lightrag-server.exe" %*
