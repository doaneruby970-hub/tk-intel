$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

& $python -m tk_intel.cli init-db
& $python -m tk_intel.cli seed-sample
& $python -m tk_intel.cli score --region MY --notes "sample pipeline"
& $python -m tk_intel.cli report

Write-Host "Sample pipeline complete. Check data\reports\latest_report.md"
