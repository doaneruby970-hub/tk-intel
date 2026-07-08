param(
    [string]$CaptureDate = "",
    [int]$LimitProducts = 100,
    [int]$LimitShops = 100
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

& $python -m pip install -r (Join-Path $root "requirements-extra.txt")
& $python -m tk_intel.cli import-findniche-my `
  --capture-date $CaptureDate `
  --limit-products $LimitProducts `
  --limit-shops $LimitShops

Write-Host "FindNiche MY import complete. Check data\reports\latest_category_scan_summary.md"
