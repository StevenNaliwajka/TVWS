@echo off
setlocal EnableExtensions

REM --- Resolve PROJECT_ROOT as the folder this .bat lives in ---
set "PROJECT_ROOT=%~dp0"
REM Remove trailing slash
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "PS1=%PROJECT_ROOT%\Codebase\Setup\setup.ps1"

if not exist "%PS1%" (
  echo ERROR: setup.ps1 not found at:
  echo   "%PS1%"
  pause
  exit /b 1
)

echo Running PowerShell setup:
echo   "%PS1%"
echo.

REM -ExecutionPolicy Bypass allows running without changing system policy
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%"

set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo Setup failed with exit code %EC%.
  pause
  exit /b %EC%
)

pause
exit /b 0
