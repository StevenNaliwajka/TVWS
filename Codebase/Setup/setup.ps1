# Codebase/Setup/setup.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# This script lives in: .../Codebase/Setup/setup.ps1
$SCRIPT_DIR  = $PSScriptRoot
$PROJECT_ROOT = (Resolve-Path (Join-Path $SCRIPT_DIR "..\..")).Path

$CREATE_VENV = Join-Path $SCRIPT_DIR "create_venv.py"
$MAKE_FOLDERS = Join-Path $SCRIPT_DIR "make_folders.py"

function Assert-FileExists([string]$Path, [string]$Name) {
    if (-not (Test-Path -Path $Path -PathType Leaf)) {
        throw "$Name not found at: $Path"
    }
}

Assert-FileExists $CREATE_VENV  "create_venv.py"
Assert-FileExists $MAKE_FOLDERS "make_folders.py"

function Get-SystemPythonCommand {
    # Prefer the Windows Python launcher if available
    if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
    throw "Python not found. Install Python 3, or ensure 'py' / 'python' is on PATH."
}

$sysPy = Get-SystemPythonCommand

Write-Host "Project root: $PROJECT_ROOT"
Write-Host "Running: create_venv.py"
& $sysPy[0] @($sysPy[1..($sysPy.Count-1)]) $CREATE_VENV

# If your venv is created at $PROJECT_ROOT\.venv (common convention), use it for the next step
$VENV_PY = Join-Path $PROJECT_ROOT ".venv\Scripts\python.exe"

if (Test-Path -Path $VENV_PY -PathType Leaf) {
    Write-Host "Using venv python: $VENV_PY"
    Write-Host "Running: make_folders.py"
    & $VENV_PY $MAKE_FOLDERS
} else {
    Write-Host "Venv python not found at: $VENV_PY"
    Write-Host "Falling back to system python for: make_folders.py"
    & $sysPy[0] @($sysPy[1..($sysPy.Count-1)]) $MAKE_FOLDERS
}

Write-Host "Setup complete."
