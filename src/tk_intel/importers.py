import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import upsert_product_snapshot


def import_generic_csv(conn, csv_path: Path | str, default_region: str = "MY") -> int:
    path = Path(csv_path)
    imported = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row.get("title") or not row.get("product_url"):
                continue
            normalized = normalize_record(row, default_region=default_region)
            upsert_product_snapshot(conn, normalized)
            imported += 1
    return imported


def normalize_record(row: dict, default_region: str = "MY") -> dict:
    captured_at = row.get("captured_at") or datetime.now(timezone(timedelta(hours=8))).isoformat()
    return {
        "product_id": clean(row.get("product_id")),
        "category_slug": clean(row.get("category_slug")),
        "keyword": clean(row.get("keyword")),
        "title": clean(row.get("title")),
        "shop_name": clean(row.get("shop_name")),
        "shop_url": clean(row.get("shop_url")),
        "product_url": clean(row.get("product_url")),
        "price": to_float(row.get("price")),
        "original_price": to_optional_float(row.get("original_price")),
        "currency": clean(row.get("currency")) or "MYR",
        "sold_count": to_int(row.get("sold_count")),
        "review_count": to_int(row.get("review_count")),
        "rating": to_float(row.get("rating")),
        "creator_count": to_int(row.get("creator_count")),
        "video_count": to_int(row.get("video_count")),
        "competitor_count": to_int(row.get("competitor_count")),
        "captured_at": captured_at,
        "source_type": clean(row.get("source_type")) or "manual_csv",
        "stock_status": clean(row.get("stock_status")),
        "raw_path": clean(row.get("raw_path")),
        "notes": clean(row.get("notes")),
        "region": clean(row.get("region")) or default_region,
    }


def seed_sample_data(conn) -> int:
    now = datetime.now(timezone(timedelta(hours=8)))
    previous = now - timedelta(days=7)
    sample_rows = [
        {
            "product_id": "1731000000000000001",
            "category_slug": "beauty-personal-care",
            "keyword": "eyeliner",
            "title": "Waterproof Eyeliner Pen",
            "shop_name": "GlamLab MY",
            "product_url": "https://shop.tiktok.com/view/product/1731000000000000001?region=MY&locale=en-MY",
            "price": 18.9,
            "original_price": 29.9,
            "currency": "MYR",
            "review_count": 320,
            "rating": 4.7,
            "creator_count": 24,
            "video_count": 78,
            "competitor_count": 42,
            "source_type": "sample_seed",
            "region": "MY",
        },
        {
            "product_id": "1731000000000000002",
            "category_slug": "muslim-fashion",
            "keyword": "baju kurung",
            "title": "Breathable Baju Kurung Set",
            "shop_name": "Wardrobe Raya MY",
            "product_url": "https://shop.tiktok.com/view/product/1731000000000000002?region=MY&locale=en-MY",
            "price": 49.0,
            "original_price": 69.0,
            "currency": "MYR",
            "review_count": 210,
            "rating": 4.6,
            "creator_count": 17,
            "video_count": 44,
            "competitor_count": 28,
            "source_type": "sample_seed",
            "region": "MY",
        },
        {
            "product_id": "1731000000000000003",
            "category_slug": "food-beverages",
            "keyword": "halal snack",
            "title": "Spicy Halal Seaweed Crisps",
            "shop_name": "SnackRush MY",
            "product_url": "https://shop.tiktok.com/view/product/1731000000000000003?region=MY&locale=en-MY",
            "price": 9.9,
            "original_price": 14.9,
            "currency": "MYR",
            "review_count": 540,
            "rating": 4.8,
            "creator_count": 31,
            "video_count": 120,
            "competitor_count": 55,
            "source_type": "sample_seed",
            "region": "MY",
        },
        {
            "product_id": "1731000000000000004",
            "category_slug": "home-supplies",
            "keyword": "organizer",
            "title": "Stackable Drawer Organizer",
            "shop_name": "HomeEase MY",
            "product_url": "https://shop.tiktok.com/view/product/1731000000000000004?region=MY&locale=en-MY",
            "price": 22.5,
            "original_price": 32.9,
            "currency": "MYR",
            "review_count": 118,
            "rating": 4.4,
            "creator_count": 11,
            "video_count": 38,
            "competitor_count": 24,
            "source_type": "sample_seed",
            "region": "MY",
        },
        {
            "product_id": "1731000000000000005",
            "category_slug": "health",
            "keyword": "supplement",
            "title": "Daily Fiber Gummies",
            "shop_name": "Wellness Corner MY",
            "product_url": "https://shop.tiktok.com/view/product/1731000000000000005?region=MY&locale=en-MY",
            "price": 39.9,
            "original_price": 55.0,
            "currency": "MYR",
            "review_count": 92,
            "rating": 4.3,
            "creator_count": 8,
            "video_count": 26,
            "competitor_count": 33,
            "source_type": "sample_seed",
            "region": "MY",
        },
    ]

    sold_pairs = [
        (640, 1180),
        (280, 430),
        (1100, 1580),
        (150, 260),
        (90, 140),
    ]
    review_pairs = [
        (250, 320),
        (160, 210),
        (470, 540),
        (90, 118),
        (70, 92),
    ]

    inserted = 0
    for base_row, sold_pair, review_pair in zip(sample_rows, sold_pairs, review_pairs, strict=True):
        first_row = dict(base_row)
        first_row["captured_at"] = previous.isoformat()
        first_row["sold_count"] = sold_pair[0]
        first_row["review_count"] = review_pair[0]
        upsert_product_snapshot(conn, first_row)
        inserted += 1

        second_row = dict(base_row)
        second_row["captured_at"] = now.isoformat()
        second_row["sold_count"] = sold_pair[1]
        second_row["review_count"] = review_pair[1]
        upsert_product_snapshot(conn, second_row)
        inserted += 1

    return inserted


def clean(value: object) -> str:
    return str(value or "").strip()


def to_int(value: object) -> int:
    if value in (None, "", "null"):
        return 0
    return int(float(str(value).replace(",", "").strip()))


def to_float(value: object) -> float:
    if value in (None, "", "null"):
        return 0.0
    return float(str(value).replace(",", "").strip())


def to_optional_float(value: object) -> float | None:
    if value in (None, "", "null"):
        return None
    return float(str(value).replace(",", "").strip())
