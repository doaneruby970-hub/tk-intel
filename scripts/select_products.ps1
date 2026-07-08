param(
    [string]$CaptureDate = "",
    [double]$MinCategoryScore = 65.0,
    [int]$TopNPerCategory = 8
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

& $python -m tk_intel.cli select-products `
  --capture-date $CaptureDate `
  --min-category-score $MinCategoryScore `
  --top-n-per-category $TopNPerCategory

Write-Host "Product selection complete. Check data\reports\latest_product_candidates.md"
