# Capture Pack Guide

- capture_date: `2026-05-10`
- keyword queue rows: `541`
- product capture slots: `1623`
- shop capture slots: `162`

## Files

- `keyword_capture_queue.csv`: one row per keyword with links and quotas
- `product_capture_slots.csv`: pre-expanded product rows to fill during scanning
- `shop_capture_slots.csv`: pre-expanded shop observation rows by category
- `search_link_queue.csv`: compact link list only

## How to use

1. Start from `keyword_capture_queue.csv` and work down by priority.
2. Open the search URLs and fill product findings into `product_capture_slots.csv`.
3. Consolidate recurring shops into `shop_capture_slots.csv`.
4. After filling rows, import those two CSV files using the category capture pipeline.

## Import filled files

```powershell
Set-Location '.'
.\scripts\run_category_capture_pipeline.ps1 `
  -SearchCsv '.\data\capture_pack\product_capture_slots.csv' `
  -ShopCsv '.\data\capture_pack\shop_capture_slots.csv' `
  -Region 'MY'
```
