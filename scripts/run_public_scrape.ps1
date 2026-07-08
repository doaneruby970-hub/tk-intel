param(
    [string]$InputCsv = ".\data\raw\product_urls_template.csv",
    [string]$Region = "MY",
    [string]$Locale = "en-MY",
    [ValidateSet("true", "false")]
    [string]$Headless = "true",
    [int]$DelayMs = 4500
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (!(Test-Path $python)) {
    throw "Missing virtual environment. Run .\scripts\bootstrap.ps1 first."
}

$inputPath = if ([System.IO.Path]::IsPathRooted($InputCsv)) { $InputCsv } else { Join-Path $root $InputCsv }
$resolvedInput = Resolve-Path -LiteralPath $inputPath
$env:PYTHONPATH = Join-Path $root "src"

& $python -m tk_intel.cli init-db
& $python -m tk_intel.cli scrape-urls --input $resolvedInput --region $Region --locale $Locale --headless $Headless --delay-ms $DelayMs
& $python -m tk_intel.cli score --region $Region --notes "public scrape pipeline"
& $python -m tk_intel.cli report

Write-Host "Public scrape pipeline complete. Check data\reports\latest_report.md"
