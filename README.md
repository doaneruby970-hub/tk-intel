# TK Product Intelligence — TikTok Shop Malaysia Product Selection Intelligence System

A local product selection MVP for TikTok Shop Malaysia (MY). Scan top-level categories → collect product snapshots → score and rank → output reports — a complete product selection intelligence pipeline.

## Features

- **Category Radar**: Three-layer radar scan (Main Category + Subcategory + Micro-Niche) across TikTok Shop MY market
- **Public Page Scraper**: Playwright-driven scraper for TikTok Shop public product pages (no login required)
- **FindNiche Data Import**: Bulk import product samples from FindNiche exported Top Sellers / Trending page HTML
- **Product Scoring**: Multi-dimensional scoring model (price band, sales volume, competition level, content fit), ranked by category
- **Micro-Niche Drilldown**: Identify niche blue-ocean opportunities within broad categories
- **SQLite Snapshots**: All collected data stored locally, supporting offline queries and longitudinal comparison
- **Category Coverage Scan**: Fully automated bulk scanning of all categories, outputting coverage reports
- **Capture Pack Workflow**: Batch collection system with keyword queue + product capture slots + shop capture slots
- **Markdown + CSV Reports**: Category reports, product candidate lists, micro-niche reports, full scan manual

## Environment Requirements

- Python 3.11+
- Playwright (Chromium browser driver required)
- Windows 10/11 (PowerShell scripts)

## Installation

```bash
git clone https://github.com/doaneruby970-hub/tk-intel.git
cd tk-intel
pip install -r requirements.txt
playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and fill in the API key (optional, only affects AI scoring module):

```env
TIKTOK_ACCESS_TOKEN=your_token_here
```

## Usage

### 1. Environment Initialization

```powershell
.\scripts\bootstrap.ps1
```

### 2. Category Radar — Full Category Scan

```powershell
.\scripts\build_category_radar.ps1
.\scripts\score_categories.ps1
```

### 3. Public Page Scraping — Collect Products by Category

```powershell
.\scripts\run_public_scrape.ps1
.\scripts\select_products.ps1
.\scripts\drilldown_products.ps1
```

### 4. FindNiche Import — Bulk Import Existing Data

```powershell
.\scripts\import_findniche_my.ps1
.\scripts\import_findniche_my_all.ps1
```

### 5. Capture Pack — Keyword Batch Collection

```powershell
.\scripts\build_capture_pack.ps1
.\scripts\run_category_capture_pipeline.ps1
```

### 6. Demo Pipeline

```powershell
.\scripts\run_sample_pipeline.ps1
```

## Notes

- This system is for market research and learning purposes only. Please comply with TikTok platform terms of use.
- The scraper uses public pages and does not require login, but control your request frequency appropriately.
- Reports and databases in the `data/` directory are generated at runtime and are included in `.gitignore`.
- CSV files in the `config/` directory are configuration data. Modify categories and keywords as needed.
