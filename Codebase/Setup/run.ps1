# Codebase/Setup/run.ps1
# Runs Codebase/run.py from PROJECT_ROOT, logs output to PROJECT_ROOT/Logs/, and pauses so the window stays open.

$ErrorActionPreference = "Stop"

function Pause-Exit {
    param([int]$Code = 0)
    Write-Host ""
    Read-Host "Press Enter to close..."
    exit $Code
}


# Pre-init so catch{} can print paths even if we fail early
$ProjectRoot = $null
$LogsDir = $null
$Log = $null

try {
    # ...\TVWS\Codebase\Setup\run.ps1 -> ...\TVWS
    $ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

    Set-Location $ProjectRoot

    $RunPy = Join-Path $ProjectRoot "Codebase\run.py"

    # --- Logs folder + timestamped log file ---
    $LogsDir = Join-Path $ProjectRoot "Logs"
    if (-not (Test-Path -Path $LogsDir -PathType Container)) {
        New-Item -Path $LogsDir -ItemType Directory | Out-Null
    }

    $Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $Log   = Join-Path $LogsDir "run_$Stamp.log"
    # -----------------------------------------

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
    $StdOutPath = Join-Path $LogsDir "run_stdout_$Stamp.tmp.txt"
    $StdErrPath = Join-Path $LogsDir "run_stderr_$Stamp.tmp.txt"

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
    Write-Host "Unhandled PowerShell error (full stack + context):"
    Write-Host "--------------------------------"

    try {
        Write-Host ("Time: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
        Write-Host ("Host: {0}" -f $Host.Name)
        Write-Host ("PS:   {0}" -f $PSVersionTable.PSVersion.ToString())
        Write-Host ""
    } catch {}

    # ErrorRecord (includes CategoryInfo, FullyQualifiedErrorId, ScriptStackTrace, etc.)
    try {
        Write-Host "ErrorRecord (Format-List * -Force):"
        Write-Host (($_ | Format-List * -Force) | Out-String)
    } catch {}

    # Invocation / position info
    try {
        if ($_.InvocationInfo) {
            Write-Host "InvocationInfo:"
            Write-Host (($_.InvocationInfo | Format-List * -Force) | Out-String)
            if ($_.InvocationInfo.PositionMessage) {
                Write-Host "PositionMessage:"
                Write-Host $_.InvocationInfo.PositionMessage
            }
        }
    } catch {}

    # Script stack trace (PowerShell)
    try {
        if ($_.ScriptStackTrace) {
            Write-Host "ScriptStackTrace:"
            Write-Host $_.ScriptStackTrace
        }
    } catch {}

    # .NET exception chain
    function _Print-ExceptionChain {
        param([Exception]$Ex)
        $i = 0
        while ($Ex -ne $null) {
            Write-Host ("Exception[{0}]: {1}" -f $i, $Ex.GetType().FullName)
            Write-Host ("Message     : {0}" -f $Ex.Message)
            if ($Ex.StackTrace) {
                Write-Host "StackTrace  :"
                Write-Host $Ex.StackTrace
            } else {
                Write-Host "StackTrace  : <none>"
            }
            Write-Host ""
            $Ex = $Ex.InnerException
            $i++
        }
    }

    try {
        if ($_.Exception) {
            Write-Host "Exception chain:"
            _Print-ExceptionChain -Ex $_.Exception
        }
    } catch {}

    # Call stack in the current scope
    try {
        Write-Host "Get-PSCallStack:"
        Write-Host ((Get-PSCallStack | Format-Table -AutoSize | Out-String))
    } catch {}

    Write-Host "--------------------------------"
    if ($ProjectRoot) {
        Write-Host "Project root:"
        Write-Host "  $ProjectRoot"
    }
    if ($Log) {
        Write-Host "Log file:"
        Write-Host "  $Log"
    } elseif ($ProjectRoot) {
        Write-Host "See logs in:"
        Write-Host ("  {0}" -f (Join-Path $ProjectRoot 'Logs'))
    }

    Pause-Exit 1
}
