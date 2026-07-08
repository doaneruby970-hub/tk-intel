param(
    [string]$CaptureDate = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$env:PYTHONPATH = Join-Path $root "src"

if ($CaptureDate) {
    & $python -m tk_intel.cli score-categories --capture-date $CaptureDate
} else {
    & $python -m tk_intel.cli score-categories
}

Write-Host "Category scoring complete. Check data\reports\latest_category_scores.md"
