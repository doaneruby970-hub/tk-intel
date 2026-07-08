param(
    [string]$CaptureDate = "",
    [int]$LimitProductsPerCategory = 50,
    [int]$LimitShopsPerCategory = 30
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

& $python -m pip install -r (Join-Path $root "requirements-extra.txt")
& $python -m tk_intel.cli import-findniche-my-all `
  --capture-date $CaptureDate `
  --limit-products-per-category $LimitProductsPerCategory `
  --limit-shops-per-category $LimitShopsPerCategory

Write-Host "FindNiche MY all-category import complete. Check data\reports\latest_category_scan_summary.md"
