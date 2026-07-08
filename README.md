# TK Product Intelligence MVP

This folder contains a local MVP for TikTok Shop Malaysia product selection work.

The system is opinionated:

- Broad scan categories first
- Collect product snapshots next
- Score products and categories last

It is designed around patterns seen in public GitHub examples:

- Public page scraping with Playwright
- Manual export from Seller Center internal APIs
- SQLite snapshots plus simple scoring/reporting

## What is included

- `config/categories_my.csv`: Malaysia category map for broad scan
- `config/keywords_my.csv`: starter keyword list by category
- `config/category_radar_my.csv`: broad category radar with MY signal and priority
- `config/category_taxonomy_my.csv`: subcategory and micro-niche research taxonomy
- `config/scan_modes_my.csv`: collection routes by research mode
- `config/category_scan_rules_my.csv`: broad-scan quotas by category
- `src/tk_intel/`: scraper, importer, SQLite, scoring, report generator
- `scripts/bootstrap.ps1`: local environment setup
- `scripts/run_sample_pipeline.ps1`: demo pipeline with seeded sample data
- `scripts/run_public_scrape.ps1`: scrape public product URLs, then score and report
- `data/raw/manual_import_template.csv`: generic CSV import template
- `data/raw/product_urls_template.csv`: public product URL input template
- `data/raw/search_capture_template.csv`: category search-result capture template
- `data/raw/shop_capture_template.csv`: category shop capture template
- `data/raw/sample_search_capture.csv`: sample category product capture rows
- `data/raw/sample_shop_capture.csv`: sample category shop capture rows
- `data/capture_pack/`: generated keyword queue and slotted capture workbooks
- `data/reports/my_category_radar.md`: generated Malaysia category radar
- `data/reports/my_keyword_pool_flat.csv`: flattened keyword pool
- `data/reports/my_scan_tasks.csv`: micro-niche scan tasks
- `data/reports/my_full_scan_playbook.md`: full-scan execution guide
- `data/reports/latest_category_scan_summary.md`: imported category-capture summary

## Research basis

The implementation follows patterns validated from these GitHub projects:

- `MisterSeitz/TikTok-Shop-Product-and-Creator-Tracker`
- `dgxnvgv-ai/tiktok-shop-manual-export-tools`
- `Phicheki/tiktok-shop-analytics`

See `RESEARCH_NOTES.md` for the breakdown.
See `CATEGORY_SOURCE_BASIS.md` for category-source provenance.

## Recommended workflow

1. Edit `config/categories_my.csv` only if you want to change category priorities.
2. Edit `config/keywords_my.csv` with the category and keyword pool you want to study.
3. Choose one of two data-entry paths:
   - Public competitor path: add product URLs to `data/raw/product_urls_template.csv`, then run the public scrape.
   - Manual import path: paste your exported CSV rows into a copy of `data/raw/manual_import_template.csv`, then import it.
4. Run scoring.
5. Read the generated report under `data/reports/`.

## Setup

```powershell
Set-Location '.'
.\scripts\bootstrap.ps1
```

## Demo run

This seeds fictional sample data so you can verify the pipeline end-to-end.

```powershell
Set-Location '.'
.\scripts\run_sample_pipeline.ps1
```

Outputs:

- SQLite database: `data/tk_intel.sqlite3`
- Latest report: `data/reports/latest_report.md`
- Latest scores: `data/reports/latest_product_scores.csv`

## Build the Malaysia category radar

```powershell
Set-Location '.'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -m tk_intel.cli build-category-radar
```

Outputs:

- `data/reports/my_category_radar.md`
- `data/reports/my_category_radar_flat.csv`

## Build the full scan system

```powershell
Set-Location '.'
.\scripts\build_scan_system.ps1
```

Outputs:

- `data/reports/my_keyword_pool_flat.csv`
- `data/reports/my_scan_tasks.csv`
- `data/reports/my_category_coverage_summary.csv`
- `data/reports/my_full_scan_playbook.md`

## Build the capture pack

This creates a ready-to-fill package so you do not need to design spreadsheets manually.

```powershell
Set-Location '.'
.\scripts\build_capture_pack.ps1
```

Outputs:

- `data/capture_pack/keyword_capture_queue.csv`
- `data/capture_pack/product_capture_slots.csv`
- `data/capture_pack/shop_capture_slots.csv`
- `data/capture_pack/search_link_queue.csv`
- `data/capture_pack/capture_pack_guide.md`

## Public product scrape

1. Copy `data/raw/product_urls_template.csv` to a working file.
2. Fill at least `product_url`, `category_slug`, and `keyword`.
3. Run:

```powershell
Set-Location '.'
.\scripts\run_public_scrape.ps1 -InputCsv '.\data\raw\product_urls_template.csv'
```

Notes:

- Public scraping is best-effort. TikTok can rate-limit or change page structure.
- A Malaysia proxy and a MY-aligned browser context improve consistency.
- This MVP is better for repeated snapshots than for one-time full-site collection.

## Import category scan captures

Fill these two templates after scanning by category:

- `data/raw/search_capture_template.csv`
- `data/raw/shop_capture_template.csv`

Then run:

```powershell
Set-Location '.'
.\scripts\run_category_capture_pipeline.ps1 `
  -SearchCsv '.\data\raw\search_capture_template.csv' `
  -ShopCsv '.\data\raw\shop_capture_template.csv' `
  -Region 'MY'
```

Outputs:

- `data/reports/latest_category_scan_summary.md`
- `data/reports/latest_category_scan_summary.csv`
- `data/reports/latest_category_product_samples.csv`
- `data/reports/latest_category_shop_samples.csv`

This step is the actual "record each category's products, shops, prices, sold counts, and ratings" layer.

## Manual CSV import

If you already have exported product rows from your own tools, import them directly:

```powershell
Set-Location '.'
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe -m tk_intel.cli init-db
.\.venv\Scripts\python.exe -m tk_intel.cli import-csv --path '.\data\raw\manual_import_template.csv'
.\.venv\Scripts\python.exe -m tk_intel.cli score --region MY
.\.venv\Scripts\python.exe -m tk_intel.cli report
```

## Scoring model

The score is not a profit guarantee. It is a screening layer.

Per product it estimates:

- `demand_score`
- `growth_score`
- `competition_score`
- `margin_proxy_score`
- `risk_score`
- `opportunity_score`

Bands:

- `>= 70`: prioritize testing
- `55-69`: keep watching
- `40-54`: cautious
- `< 40`: crowded or weak

## Why category-first

The intended use is:

1. Broad scan 20+ categories
2. Pick 3-5 categories with better category scores
3. Deep track products inside those categories
4. Move to supplier and margin validation only after that

That keeps the workflow from drifting into "collect everything, understand nothing."
