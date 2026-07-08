param(
    [string]$CaptureDate = "",
    [int]$ProductSlotsPerKeyword = 5,
    [int]$ShopSlotsPerCategory = 12
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

& $python -m tk_intel.cli build-capture-pack `
  --capture-date $CaptureDate `
  --product-slots-per-keyword $ProductSlotsPerKeyword `
  --shop-slots-per-category $ShopSlotsPerCategory

Write-Host "Capture pack build complete. Check data\capture_pack\capture_pack_guide.md"
