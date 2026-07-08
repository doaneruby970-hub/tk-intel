param(
    [string]$SearchCsv = ".\data\raw\search_capture_template.csv",
    [string]$ShopCsv = ".\data\raw\shop_capture_template.csv",
    [string]$Region = "MY",
    [string]$CaptureDate = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$searchInput = if ([System.IO.Path]::IsPathRooted($SearchCsv)) { $SearchCsv } else { Join-Path $root $SearchCsv }
$shopInput = if ([System.IO.Path]::IsPathRooted($ShopCsv)) { $ShopCsv } else { Join-Path $root $ShopCsv }

$env:PYTHONPATH = Join-Path $root "src"

& $python -m tk_intel.cli init-db
& $python -m tk_intel.cli import-search-capture --path $searchInput --region $Region
& $python -m tk_intel.cli import-shop-capture --path $shopInput

if ($CaptureDate) {
    & $python -m tk_intel.cli report-category-capture --capture-date $CaptureDate
} else {
    & $python -m tk_intel.cli report-category-capture
}

Write-Host "Category capture pipeline complete. Check data\reports\latest_category_scan_summary.md"
