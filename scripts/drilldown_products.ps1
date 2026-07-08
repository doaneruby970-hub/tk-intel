param(
    [string]$ProductCandidates = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

if ($ProductCandidates) {
    & $python -m tk_intel.cli drilldown-products --product-candidates $ProductCandidates
} else {
    & $python -m tk_intel.cli drilldown-products
}

Write-Host "Product drilldown complete. Check data\reports\latest_micro_niche_summary.md"
