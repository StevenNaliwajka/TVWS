$ErrorActionPreference = "Stop"

# cd to project root (folder containing Codebase/)
$here = $PSScriptRoot
if (Test-Path (Join-Path $here "Codebase")) { Set-Location $here } else { Set-Location (Join-Path $here "..") }

$py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Couldn't find venv python at $py" }

$dir = Read-Host "Enter the directory to process"
if (-not (Test-Path $dir -PathType Container)) { throw "Folder not found: $dir" }

& $py -m Codebase.UugaDuuga --root "$dir"
& $py -m Codebase.ToFSheetAverage --root "$dir"
& $py -m Codebase.ToFSheetAverageAdd --root "$dir"

Write-Host "All scripts completed successfully."
