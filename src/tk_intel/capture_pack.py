import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

from .scanplan import build_scan_system
from .settings import CAPTURE_PACK_DIR, REPORTS_DIR


TZ_UTC8 = timezone(timedelta(hours=8))


def build_capture_pack(
    output_dir: Path | str = CAPTURE_PACK_DIR,
    capture_date: str | None = None,
    product_slots_per_keyword: int = 5,
    shop_slots_per_category: int = 12,
) -> dict[str, Path]:
    build_scan_system(output_dir=REPORTS_DIR)

    keyword_rows = _read_csv(REPORTS_DIR / "my_keyword_pool_flat.csv")
    task_rows = _read_csv(REPORTS_DIR / "my_scan_tasks.csv")
    coverage_rows = _read_csv(REPORTS_DIR / "my_category_coverage_summary.csv")

    chosen_date = capture_date or datetime.now(TZ_UTC8).date().isoformat()
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    queue_rows = build_keyword_queue_rows(keyword_rows, task_rows, chosen_date)
    product_slot_rows = build_product_slot_rows(queue_rows, product_slots_per_keyword)
    shop_slot_rows = build_shop_slot_rows(coverage_rows, task_rows, chosen_date, shop_slots_per_category)
    link_rows = build_link_rows(queue_rows)

    keyword_queue_path = output_root / "keyword_capture_queue.csv"
    product_slots_path = output_root / "product_capture_slots.csv"
    shop_slots_path = output_root / "shop_capture_slots.csv"
    links_path = output_root / "search_link_queue.csv"
    readme_path = output_root / "capture_pack_guide.md"

    _write_csv(keyword_queue_path, queue_rows)
    _write_csv(product_slots_path, product_slot_rows)
    _write_csv(shop_slots_path, shop_slot_rows)
    _write_csv(links_path, link_rows)
    _write_guide(readme_path, chosen_date, queue_rows, product_slot_rows, shop_slot_rows)

    return {
        "keyword_queue_path": keyword_queue_path,
        "product_slots_path": product_slots_path,
        "shop_slots_path": shop_slots_path,
        "links_path": links_path,
        "guide_path": readme_path,
    }


def build_keyword_queue_rows(keyword_rows: list[dict], task_rows: list[dict], capture_date: str) -> list[dict]:
    task_lookup: dict[tuple[str, str, str], dict] = {
        (row["broad_category_slug"], row["sub_category"], row["micro_niche"]): row for row in task_rows
    }
    category_name_by_slug = {
        row["broad_category_slug"]: row["broad_category_name"]
        for row in task_rows
        if row.get("broad_category_name")
    }
    queue_rows = []
    for index, row in enumerate(keyword_rows, start=1):
        task = task_lookup.get((row["broad_category_slug"], row["sub_category"], row["micro_niche"]), {})
        queue_rows.append(
            {
                "queue_id": f"KW-{index:04d}",
                "capture_date": capture_date,
                "broad_category_slug": row["broad_category_slug"],
                "broad_category_name": row["broad_category_name"] or task.get("broad_category_name", "") or category_name_by_slug.get(row["broad_category_slug"], ""),
                "sub_category": row["sub_category"],
                "micro_niche": row["micro_niche"],
                "keyword": row["keyword"],
                "source_level": row["source_level"],
                "research_priority": row["research_priority"] or task.get("scan_priority", ""),
                "my_fit": row["my_fit"],
                "selection_mode": row["selection_mode"],
                "entrypoints": row["entrypoints"],
                "primary_goal": row["primary_goal"],
                "product_target_per_keyword": task.get("product_target_per_keyword", ""),
                "shop_target_per_keyword": task.get("shop_target_per_keyword", ""),
                "video_target_per_keyword": task.get("video_target_per_keyword", ""),
                "live_target_per_keyword": task.get("live_target_per_keyword", ""),
                "refresh_days": task.get("refresh_days", ""),
                "tiktok_search_url": make_tiktok_search_url(row["keyword"]),
                "tiktok_tag_url": make_tiktok_tag_url(row["keyword"]),
                "google_shop_query_url": make_google_shop_query_url(row["keyword"]),
                "status": "todo",
                "notes": "",
            }
        )
    return queue_rows


def build_product_slot_rows(queue_rows: list[dict], slots_per_keyword: int) -> list[dict]:
    rows = []
    for item in queue_rows:
        for rank in range(1, slots_per_keyword + 1):
            rows.append(
                {
                    "queue_id": item["queue_id"],
                    "capture_date": item["capture_date"],
                    "broad_category_slug": item["broad_category_slug"],
                    "sub_category": item["sub_category"],
                    "micro_niche": item["micro_niche"],
                    "keyword": item["keyword"],
                    "rank": rank,
                    "shop_name": "",
                    "product_title": "",
                    "price": "",
                    "currency": "MYR",
                    "sold_count": "",
                    "review_count": "",
                    "rating": "",
                    "product_url": "",
                    "shop_url": "",
                    "video_flag": "",
                    "live_flag": "",
                    "notes": "",
                    "tiktok_search_url": item["tiktok_search_url"],
                    "tiktok_tag_url": item["tiktok_tag_url"],
                    "google_shop_query_url": item["google_shop_query_url"],
                }
            )
    return rows


def build_shop_slot_rows(coverage_rows: list[dict], task_rows: list[dict], capture_date: str, slots_per_category: int) -> list[dict]:
    keywords_by_category: dict[str, list[str]] = {}
    for row in task_rows:
        slug = row["broad_category_slug"]
        existing = keywords_by_category.setdefault(slug, [])
        for keyword in split_keywords(row["starter_keywords"]):
            if keyword not in existing:
                existing.append(keyword)

    rows = []
    for category in coverage_rows:
        slug = category["broad_category_slug"]
        keywords = keywords_by_category.get(slug, [])[:6]
        for slot in range(1, slots_per_category + 1):
            rows.append(
                {
                    "category_slot_id": f"{slug}-SHOP-{slot:02d}",
                    "capture_date": capture_date,
                    "broad_category_slug": slug,
                    "shop_name": "",
                    "shop_url": "",
                    "category_focus": "",
                    "shop_rating": "",
                    "product_count": "",
                    "hero_products": "",
                    "price_band": "",
                    "content_style": "",
                    "live_intensity": "",
                    "notes": "",
                    "recommended_keywords": " | ".join(keywords),
                    "recommended_search_url": make_tiktok_search_url(keywords[0]) if keywords else "",
                }
            )
    return rows


def build_link_rows(queue_rows: list[dict]) -> list[dict]:
    return [
        {
            "queue_id": row["queue_id"],
            "broad_category_slug": row["broad_category_slug"],
            "sub_category": row["sub_category"],
            "micro_niche": row["micro_niche"],
            "keyword": row["keyword"],
            "tiktok_search_url": row["tiktok_search_url"],
            "tiktok_tag_url": row["tiktok_tag_url"],
            "google_shop_query_url": row["google_shop_query_url"],
        }
        for row in queue_rows
    ]


def make_tiktok_search_url(keyword: str) -> str:
    return f"https://www.tiktok.com/search?q={quote_plus(keyword)}"


def make_tiktok_tag_url(keyword: str) -> str:
    slug = "-".join([part for part in keyword.lower().split() if part])
    return f"https://www.tiktok.com/tag/{slug}"


def make_google_shop_query_url(keyword: str) -> str:
    query = f'site:shop.tiktok.com/view/product "{keyword}" Malaysia'
    return f"https://www.google.com/search?q={quote_plus(query)}"


def _write_guide(path: Path, capture_date: str, queue_rows: list[dict], product_rows: list[dict], shop_rows: list[dict]) -> None:
    lines = [
        "# Capture Pack Guide",
        "",
        f"- capture_date: `{capture_date}`",
        f"- keyword queue rows: `{len(queue_rows)}`",
        f"- product capture slots: `{len(product_rows)}`",
        f"- shop capture slots: `{len(shop_rows)}`",
        "",
        "## Files",
        "",
        "- `keyword_capture_queue.csv`: one row per keyword with links and quotas",
        "- `product_capture_slots.csv`: pre-expanded product rows to fill during scanning",
        "- `shop_capture_slots.csv`: pre-expanded shop observation rows by category",
        "- `search_link_queue.csv`: compact link list only",
        "",
        "## How to use",
        "",
        "1. Start from `keyword_capture_queue.csv` and work down by priority.",
        "2. Open the search URLs and fill product findings into `product_capture_slots.csv`.",
        "3. Consolidate recurring shops into `shop_capture_slots.csv`.",
        "4. After filling rows, import those two CSV files using the category capture pipeline.",
        "",
        "## Import filled files",
        "",
        "```powershell",
        "Set-Location 'E:\\TK情报信息\\TK选品'",
        ".\\scripts\\run_category_capture_pipeline.ps1 `",
        "  -SearchCsv '.\\data\\capture_pack\\product_capture_slots.csv' `",
        "  -ShopCsv '.\\data\\capture_pack\\shop_capture_slots.csv' `",
        "  -Region 'MY'",
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_keywords(raw: str) -> list[str]:
    return [part.strip() for part in str(raw or "").split("|") if part.strip()]


def _read_csv(path: Path | str) -> list[dict]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
