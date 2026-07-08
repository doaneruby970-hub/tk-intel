# Research Notes

This file summarizes how the local MVP was shaped from public GitHub examples checked on 2026-05-10.

## Reference repos

### 1) MisterSeitz/TikTok-Shop-Product-and-Creator-Tracker

Observed pattern:

- Python plus Playwright
- Track product metadata, price, stock, ratings, creator-linked videos
- Save snapshots across runs
- Region support includes `MY`

What was adopted here:

- Public-page first architecture
- Snapshot-based model instead of one-off scrape model
- Region-aware scraping assumptions

Not copied:

- Apify-specific runtime and storage
- Notification layer

### 2) dgxnvgv-ai/tiktok-shop-manual-export-tools

Observed pattern:

- Local Playwright scripts
- Seller Center login flow
- Uses internal product-manage and product-analysis APIs instead of DOM scraping
- Writes JSON and CSV exports per run

What was adopted here:

- Keep a manual import path separate from public competitor scraping
- Persist snapshots and raw export metadata
- Treat "manual export" as a stable ingestion source for owned accounts

Not copied:

- Seller Center-specific UI server
- Merchant-login bound workflow

### 3) Phicheki/tiktok-shop-analytics

Observed pattern:

- Dashboard plus scoring layer
- Hidden-gem style formula
- Mix of scraper and optional API mode

What was adopted here:

- Simple score-first reporting mindset
- Category plus product ranking
- Output that can drive selection decisions, not just raw data storage

Not copied:

- FastAPI and frontend stack
- Mock/real API split

## Design decisions for this local MVP

### Chosen stack

- Python
- SQLite
- Playwright
- CSV and Markdown exports

Reason:

- Lowest operational overhead
- Easy to keep under one local folder
- Good enough for repeated MY-market snapshots

### Why not full-category auto-discovery

The public GitHub examples themselves show the core limitation:

- Seller Center internal APIs are stable but account-scoped
- Public competitor discovery is unstable and front-end dependent

So this MVP does not pretend to "collect all MY categories automatically."
It gives you:

- category map
- keyword map
- product URL scrape path
- generic CSV import path
- scoring plus reporting

That is enough to start real category research without overengineering.
