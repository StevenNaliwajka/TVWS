# Codebase/Setup/run.ps1
# Runs Codebase/run.py from PROJECT_ROOT, logs output, and pauses so the window stays open.

$ErrorActionPreference = "Stop"

function Pause-Exit {
    param([int]$Code = 0)
    Write-Host ""
    Read-Host "Press Enter to close..."
    exit $Code
}

try {
    # ...\TVWS\Codebase\Setup\run.ps1 -> ...\TVWS
    $ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

    Set-Location $ProjectRoot

    $RunPy = Join-Path $ProjectRoot "Codebase\run.py"
    $Log   = Join-Path $ProjectRoot "run_log.txt"

    if (-not (Test-Path -Path $RunPy -PathType Leaf)) {
        Write-Host "ERROR: run.py not found at:"
        Write-Host "  $RunPy"
        Pause-Exit 1
    }

    # Pick Python: prefer project .venv, then py -3, then python, then python3
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

    $PythonExe  = $null
    $PythonArgs = @()

    if (Test-Path -Path $VenvPython -PathType Leaf) {
        $PythonExe  = $VenvPython
        $PythonArgs = @()
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe  = "py"
        $PythonArgs = @("-3")
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe  = "python"
        $PythonArgs = @()
    }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
        $PythonExe  = "python3"
        $PythonArgs = @()
    }
    else {
        Write-Host "ERROR: Python not found (.venv/py/python/python3)."
        Pause-Exit 1
    }


    $AllArgs = @()
    $AllArgs += $PythonArgs
    $AllArgs += @("-X","faulthandler","-u","-m","Codebase.run")

    Write-Host "Running:"
    Write-Host "  $PythonExe $($AllArgs -join ' ')"
    Write-Host ""
    Write-Host "Logging output to:"
    Write-Host "  $Log"
    Write-Host ""

    # Always write a header to the log first
    "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ====" | Out-File -FilePath $Log -Append -Encoding utf8
    "CWD: $ProjectRoot" | Out-File -FilePath $Log -Append -Encoding utf8
    "CMD: $PythonExe $($AllArgs -join ' ')" | Out-File -FilePath $Log -Append -Encoding utf8
    "" | Out-File -FilePath $Log -Append -Encoding utf8

    # Capture stdout/stderr to temp files (avoids pipe/Tee issues)
    $StdOutPath = Join-Path $ProjectRoot "run_stdout.tmp.txt"
    $StdErrPath = Join-Path $ProjectRoot "run_stderr.tmp.txt"

    if (Test-Path $StdOutPath) { Remove-Item $StdOutPath -Force }
    if (Test-Path $StdErrPath) { Remove-Item $StdErrPath -Force }

    $p = Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $AllArgs `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $StdOutPath `
        -RedirectStandardError  $StdErrPath

    $ec = $p.ExitCode

    $stdout = ""
    $stderr = ""

    if (Test-Path $StdOutPath) { $stdout = Get-Content $StdOutPath -Raw }
    if (Test-Path $StdErrPath) { $stderr = Get-Content $StdErrPath -Raw }

    # Print and log captured output
    if ($stdout) { Write-Host $stdout }
    if ($stderr) { Write-Host $stderr }

    $stdout | Out-File -FilePath $Log -Append -Encoding utf8
    $stderr | Out-File -FilePath $Log -Append -Encoding utf8

    # Clean temp files (optional)
    if (Test-Path $StdOutPath) { Remove-Item $StdOutPath -Force }
    if (Test-Path $StdErrPath) { Remove-Item $StdErrPath -Force }

    Write-Host ""
    if ($ec -ne 0) {
        Write-Host "Run failed with exit code $ec."
        Write-Host "See log:"
        Write-Host "  $Log"
        Pause-Exit $ec
    }

    Write-Host "Run completed successfully."
    Pause-Exit 0
}
catch {
    Write-Host ""
    Write-Host "Unhandled error (full details):"
    Write-Host "--------------------------------"
    Write-Host ($_ | Out-String)
    if ($_.Exception) {
        Write-Host "Exception:"
        Write-Host ($_.Exception | Format-List * -Force | Out-String)
    }
    Write-Host "--------------------------------"
    Write-Host "See log (if created) in project root: run_log.txt"
    Pause-Exit 1
}
