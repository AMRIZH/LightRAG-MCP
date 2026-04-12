@echo off
setlocal EnableExtensions

set URL=http://127.0.0.1:9621/health
if not "%~1"=="" set "URL=%~1"

powershell -NoProfile -Command "& { param([string]$u) $ErrorActionPreference='Stop'; $uri = $null; if(-not [System.Uri]::TryCreate($u, [System.UriKind]::Absolute, [ref]$uri)) { throw 'Invalid URL' }; if($uri.Scheme -notin @('http','https')) { throw 'Only http/https URLs are allowed' }; $r = Invoke-RestMethod -Uri $uri -Method Get -TimeoutSec 15; $r | ConvertTo-Json -Depth 10 }" "%URL%"
if errorlevel 1 (
  echo Healthcheck failed for %URL%
  exit /b 1
)

echo Healthcheck succeeded.
