@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "PS1=%PROJECT_ROOT%\Codebase\Setup\run.ps1"

if not exist "%PS1%" (
  echo ERROR: run.ps1 not found at:
  echo   "%PS1%"
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
exit /b %ERRORLEVEL%
