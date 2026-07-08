import csv
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import fetch_rows, upsert_product_snapshot
from .settings import REPORTS_DIR


TZ_UTC8 = timezone(timedelta(hours=8))


def import_search_capture_csv(conn, csv_path: Path | str, region: str = "MY") -> int:
    path = Path(csv_path)
    imported = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not clean(row.get("broad_category_slug")) or not clean(row.get("product_title")):
                continue
            normalized = normalize_search_row(row, region=region)
            conn.execute(
                """
                INSERT OR REPLACE INTO category_product_samples (
                    capture_date, broad_category_slug, sub_category, micro_niche, keyword, rank,
                    shop_name, product_title, price, currency, sold_count, review_count, rating,
                    product_url, shop_url, video_flag, live_flag, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["capture_date"],
                    normalized["broad_category_slug"],
                    normalized["sub_category"],
                    normalized["micro_niche"],
                    normalized["keyword"],
                    normalized["rank"],
                    normalized["shop_name"],
                    normalized["product_title"],
                    normalized["price"],
                    normalized["currency"],
                    normalized["sold_count"],
                    normalized["review_count"],
                    normalized["rating"],
                    normalized["product_url"],
                    normalized["shop_url"],
                    normalized["video_flag"],
                    normalized["live_flag"],
                    normalized["notes"],
                ),
            )

            upsert_product_snapshot(
                conn,
                {
                    "product_id": extract_product_id(normalized["product_url"]),
                    "category_slug": normalized["broad_category_slug"],
                    "keyword": normalized["keyword"],
                    "title": normalized["product_title"],
                    "shop_name": normalized["shop_name"],
                    "shop_url": normalized["shop_url"],
                    "product_url": normalized["product_url"],
                    "price": normalized["price"],
                    "currency": normalized["currency"],
                    "sold_count": normalized["sold_count"],
                    "review_count": normalized["review_count"],
                    "rating": normalized["rating"],
                    "creator_count": normalized["video_flag"],
                    "video_count": normalized["video_flag"],
                    "competitor_count": 0,
                    "captured_at": normalized["captured_at"],
                    "source_type": "category_search_capture",
                    "notes": normalized["notes"],
                    "region": region,
                },
            )
            imported += 1
    conn.commit()
    return imported


def import_shop_capture_csv(conn, csv_path: Path | str) -> int:
    path = Path(csv_path)
    imported = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not clean(row.get("broad_category_slug")) or not clean(row.get("shop_name")):
                continue
            normalized = normalize_shop_row(row)
            conn.execute(
                """
                INSERT OR REPLACE INTO category_shop_samples (
                    capture_date, broad_category_slug, shop_name, shop_url, category_focus,
                    shop_rating, product_count, hero_products, price_band, content_style,
                    live_intensity, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["capture_date"],
                    normalized["broad_category_slug"],
                    normalized["shop_name"],
                    normalized["shop_url"],
                    normalized["category_focus"],
                    normalized["shop_rating"],
                    normalized["product_count"],
                    normalized["hero_products"],
                    normalized["price_band"],
                    normalized["content_style"],
                    normalized["live_intensity"],
                    normalized["notes"],
                ),
            )
            imported += 1
    conn.commit()
    return imported


def export_category_capture_reports(conn, output_dir: Path | str = REPORTS_DIR, capture_date: str | None = None) -> dict[str, Path]:
    selected_date = capture_date or latest_capture_date(conn)
    if not selected_date:
        raise RuntimeError("No category capture data found.")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_rows = category_summary_rows(conn, selected_date)
    product_rows = captured_product_rows(conn, selected_date)
    shop_rows = captured_shop_rows(conn, selected_date)

    summary_csv = output_root / "latest_category_scan_summary.csv"
    summary_md = output_root / "latest_category_scan_summary.md"
    product_csv = output_root / "latest_category_product_samples.csv"
    shop_csv = output_root / "latest_category_shop_samples.csv"

    write_csv(summary_csv, summary_rows)
    write_csv(product_csv, product_rows)
    write_csv(shop_csv, shop_rows)
    write_summary_markdown(summary_md, selected_date, summary_rows, product_rows)

    return {
        "summary_csv": summary_csv,
        "summary_md": summary_md,
        "product_csv": product_csv,
        "shop_csv": shop_csv,
    }


def latest_capture_date(conn) -> str | None:
    row = conn.execute(
        """
        SELECT capture_date
        FROM category_product_samples
        ORDER BY capture_date DESC
        LIMIT 1
        """
    ).fetchone()
    return None if row is None else str(row["capture_date"])


def category_summary_rows(conn, capture_date: str) -> list[dict]:
    product_rows = captured_product_rows(conn, capture_date)
    shop_rows = captured_shop_rows(conn, capture_date)

    shops_by_category: dict[str, list[dict]] = defaultdict(list)
    for row in shop_rows:
        shops_by_category[row["broad_category_slug"]].append(row)

    keywords_by_category: dict[str, Counter] = defaultdict(Counter)
    shop_counter_by_category: dict[str, Counter] = defaultdict(Counter)
    for row in product_rows:
        keywords_by_category[row["broad_category_slug"]][row["keyword"]] += 1
        label = row["shop_name"] or row["shop_url"] or ""
        if label:
            shop_counter_by_category[row["broad_category_slug"]][label] += 1

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in product_rows:
        grouped[row["broad_category_slug"]].append(row)

    category_meta = {
        row["category_slug"]: row["category_name"]
        for row in fetch_rows(conn, "SELECT category_slug, category_name FROM categories")
    }

    output = []
    for slug, rows in grouped.items():
        shop_rows_for_category = shops_by_category.get(slug, [])
        avg_shop_rating = average([to_float(item["shop_rating"]) for item in shop_rows_for_category])
        avg_shop_product_count = average([to_float(item["product_count"]) for item in shop_rows_for_category])

        output.append(
            {
                "capture_date": capture_date,
                "broad_category_slug": slug,
                "broad_category_name": category_meta.get(slug, slug),
                "product_sample_count": len(rows),
                "unique_product_count": len({row["product_url"] or row["product_title"] for row in rows}),
                "unique_shop_count": len({(row["shop_url"] or row["shop_name"]) for row in rows if (row["shop_url"] or row["shop_name"])}),
                "shop_observation_count": len(shop_rows_for_category),
                "avg_price": round(average([to_float(row["price"]) for row in rows]), 2),
                "min_price": round(min([to_float(row["price"]) for row in rows], default=0.0), 2),
                "max_price": round(max([to_float(row["price"]) for row in rows], default=0.0), 2),
                "avg_sold_count": round(average([to_float(row["sold_count"]) for row in rows]), 2),
                "total_visible_sold": int(sum([to_float(row["sold_count"]) for row in rows])),
                "avg_review_count": round(average([to_float(row["review_count"]) for row in rows]), 2),
                "avg_rating": round(average([to_float(row["rating"]) for row in rows]), 2),
                "video_share_pct": round(average([100.0 * to_float(row["video_flag"]) for row in rows]), 1),
                "live_share_pct": round(average([100.0 * to_float(row["live_flag"]) for row in rows]), 1),
                "avg_shop_rating": round(avg_shop_rating, 2),
                "avg_shop_product_count": round(avg_shop_product_count, 2),
                "top_keywords": join_top(keywords_by_category[slug]),
                "top_shops": join_top(shop_counter_by_category[slug]),
            }
        )

    output.sort(key=lambda item: (-item["product_sample_count"], -item["unique_shop_count"], item["broad_category_slug"]))
    return output


def captured_product_rows(conn, capture_date: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            capture_date,
            broad_category_slug,
            sub_category,
            micro_niche,
            keyword,
            rank,
            shop_name,
            product_title,
            price,
            currency,
            sold_count,
            review_count,
            rating,
            product_url,
            shop_url,
            video_flag,
            live_flag,
            notes
        FROM category_product_samples
        WHERE capture_date = ?
        ORDER BY broad_category_slug, keyword, rank, sold_count DESC
        """,
        (capture_date,),
    )
    return [dict(row) for row in rows]


def captured_shop_rows(conn, capture_date: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            capture_date,
            broad_category_slug,
            shop_name,
            shop_url,
            category_focus,
            shop_rating,
            product_count,
            hero_products,
            price_band,
            content_style,
            live_intensity,
            notes
        FROM category_shop_samples
        WHERE capture_date = ?
        ORDER BY broad_category_slug, shop_rating DESC, product_count DESC
        """,
        (capture_date,),
    )
    return [dict(row) for row in rows]


def write_summary_markdown(path: Path, capture_date: str, summary_rows: list[dict], product_rows: list[dict]) -> None:
    lines = [
        "# Category Scan Summary",
        "",
        f"- capture_date: `{capture_date}`",
        f"- categories with samples: `{len(summary_rows)}`",
        f"- product sample rows: `{len(product_rows)}`",
        "",
        "## Category summary",
        "",
        "| category | product samples | unique shops | avg price | avg sold | avg rating | avg shop rating | top keywords |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {broad_category_name} | {product_sample_count} | {unique_shop_count} | {avg_price} | {avg_sold_count} | {avg_rating} | {avg_shop_rating} | {top_keywords} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## What this is for",
            "",
            "1. Confirm that each broad category actually has enough sampled products and shops.",
            "2. Compare price bands, visible sold counts, and rating levels before category scoring.",
            "3. Use the exported CSV files as the direct input to later category-scoring logic.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def normalize_search_row(row: dict, region: str = "MY") -> dict:
    capture_date = clean(row.get("capture_date")) or datetime.now(TZ_UTC8).date().isoformat()
    captured_at = f"{capture_date}T12:00:00+08:00"
    return {
        "capture_date": capture_date,
        "captured_at": captured_at,
        "broad_category_slug": clean(row.get("broad_category_slug")),
        "sub_category": clean(row.get("sub_category")),
        "micro_niche": clean(row.get("micro_niche")),
        "keyword": clean(row.get("keyword")),
        "rank": to_int(row.get("rank")),
        "shop_name": clean(row.get("shop_name")),
        "product_title": clean(row.get("product_title")),
        "price": to_float(row.get("price")),
        "currency": clean(row.get("currency")) or "MYR",
        "sold_count": to_int(row.get("sold_count")),
        "review_count": to_int(row.get("review_count")),
        "rating": to_float(row.get("rating")),
        "product_url": clean(row.get("product_url")),
        "shop_url": clean(row.get("shop_url")),
        "video_flag": to_bool_int(row.get("video_flag")),
        "live_flag": to_bool_int(row.get("live_flag")),
        "notes": clean(row.get("notes")),
        "region": region,
    }


def normalize_shop_row(row: dict) -> dict:
    capture_date = clean(row.get("capture_date")) or datetime.now(TZ_UTC8).date().isoformat()
    return {
        "capture_date": capture_date,
        "broad_category_slug": clean(row.get("broad_category_slug")),
        "shop_name": clean(row.get("shop_name")),
        "shop_url": clean(row.get("shop_url")),
        "category_focus": clean(row.get("category_focus")),
        "shop_rating": to_float(row.get("shop_rating")),
        "product_count": to_int(row.get("product_count")),
        "hero_products": clean(row.get("hero_products")),
        "price_band": clean(row.get("price_band")),
        "content_style": clean(row.get("content_style")),
        "live_intensity": clean(row.get("live_intensity")),
        "notes": clean(row.get("notes")),
    }


def extract_product_id(product_url: str) -> str:
    match = re.search(r"/product/(\d+)", product_url or "")
    return "" if match is None else match.group(1)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def join_top(counter: Counter, limit: int = 3) -> str:
    parts = [name for name, _ in counter.most_common(limit) if name]
    return " | ".join(parts)


def average(values: list[float]) -> float:
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return 0.0
    return sum(clean_values) / len(clean_values)


def to_bool_int(value: object) -> int:
    text = clean(value).lower()
    if text in {"1", "true", "yes", "y"}:
        return 1
    return 0


def to_int(value: object) -> int:
    if value in (None, "", "null"):
        return 0
    return int(float(str(value).replace(",", "").strip()))


def to_float(value: object) -> float:
    if value in (None, "", "null"):
        return 0.0
    return float(str(value).replace(",", "").strip())


def clean(value: object) -> str:
    return str(value or "").strip()
