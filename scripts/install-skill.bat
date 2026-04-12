@echo off
setlocal EnableExtensions

set "SRC=%~dp0..\skills\lightrag-academic-writing"
if not exist "%SRC%\SKILL.md" (
  echo Skill source not found: %SRC%\SKILL.md
  exit /b 1
)

set "VSCODE_SKILLS=%APPDATA%\Code\User\prompts\skills\lightrag-academic-writing"
set "AGENTS_SKILLS=%USERPROFILE%\.agents\skills\lightrag-academic-writing"

echo Installing skill to VS Code prompts path...
if not exist "%VSCODE_SKILLS%" mkdir "%VSCODE_SKILLS%"
copy /Y "%SRC%\SKILL.md" "%VSCODE_SKILLS%\SKILL.md" >nul || (
  echo Failed to copy SKILL.md to VS Code prompts path.
  exit /b 1
)
copy /Y "%SRC%\pressure-scenarios.md" "%VSCODE_SKILLS%\pressure-scenarios.md" >nul || (
  echo Failed to copy pressure-scenarios.md to VS Code prompts path.
  exit /b 1
)

echo Installing skill to Codex agent path...
if not exist "%AGENTS_SKILLS%" mkdir "%AGENTS_SKILLS%"
copy /Y "%SRC%\SKILL.md" "%AGENTS_SKILLS%\SKILL.md" >nul || (
  echo Failed to copy SKILL.md to Codex agent path.
  exit /b 1
)
copy /Y "%SRC%\pressure-scenarios.md" "%AGENTS_SKILLS%\pressure-scenarios.md" >nul || (
  echo Failed to copy pressure-scenarios.md to Codex agent path.
  exit /b 1
)

echo Skill installed:
echo   %VSCODE_SKILLS%
echo   %AGENTS_SKILLS%
