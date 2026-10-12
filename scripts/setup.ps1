[CmdletBinding()]
param([switch]$CpuOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 virtual environment creation failed.' }
}
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$wheelIndex = if ($CpuOnly) { 'https://download.pytorch.org/whl/cpu' } else { 'https://download.pytorch.org/whl/cu128' }
& $pythonExe -m pip install 'torch==2.10.0' --index-url $wheelIndex
if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
& $pythonExe -m pip install -r requirements-tested.txt -e .
if ($LASTEXITCODE -ne 0) { throw 'Project dependency installation failed.' }
& $pythonExe -m forge1 doctor
if ($LASTEXITCODE -ne 0) { throw 'Environment validation failed.' }
Write-Output 'Ready. Run .\.venv\Scripts\python.exe scripts/smoke.py --output runs/smoke --device cpu'
