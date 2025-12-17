@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "PS1=%PROJECT_ROOT%\Codebase\Setup\run.ps1"
set "LOG=%PROJECT_ROOT%\Logs\run_transcript.txt"

echo PROJECT_ROOT = "%PROJECT_ROOT%"
echo PS1          = "%PS1%"
echo LOG          = "%LOG%"
echo.

if not exist "%PS1%" (
  echo ERROR: run.ps1 not found at:
  echo   "%PS1%"
  pause
  exit /b 1
)

echo [run.bat] Starting PowerShell...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "& { $ErrorActionPreference='Stop'; " ^
  "  Start-Transcript -Path '%LOG%' -Force | Out-Null; " ^
  "  Set-PSDebug -Trace 1; " ^
  "  & '%PS1%'; " ^
  "  $rc = if ($LASTEXITCODE) { $LASTEXITCODE } else { 0 }; " ^
  "  Set-PSDebug -Off; " ^
  "  Stop-Transcript | Out-Null; " ^
  "  exit $rc }"

set "RC=%ERRORLEVEL%"
echo.
echo [run.bat] PowerShell returned %RC%
echo [run.bat] Transcript: "%LOG%"
pause
exit /b %RC%
