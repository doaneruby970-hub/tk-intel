import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .category_capture import export_category_capture_reports
from .settings import RAW_DIR


TZ_UTC8 = timezone(timedelta(hours=8))
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
TRENDING_URL = "https://findniche.com/zh/tiktok/trending-products-my"
TOP_SELLERS_URL = "https://findniche.com/my/top-tiktok-seller"
BASE_URL = "https://findniche.com"


def import_findniche_my(conn, capture_date: str | None = None, limit_products: int = 100, limit_shops: int = 100) -> dict:
    chosen_date = capture_date or datetime.now(TZ_UTC8).date().isoformat()
    cleanup_existing_findniche_rows(conn, chosen_date)

    trending_html = fetch_html(TRENDING_URL)
    shops_html = fetch_html(TOP_SELLERS_URL)

    (RAW_DIR / "findniche_trending_products_my.html").write_text(trending_html, encoding="utf-8")
    (RAW_DIR / "findniche_top_sellers_my.html").write_text(shops_html, encoding="utf-8")

    product_rows = parse_trending_products(trending_html, chosen_date, limit_products)
    shop_rows = parse_top_shops(shops_html, chosen_date, limit_shops)

    insert_product_rows(conn, product_rows)
    insert_shop_rows(conn, shop_rows)
    conn.commit()

    reports = export_category_capture_reports(conn, capture_date=chosen_date)
    return {
        "capture_date": chosen_date,
        "product_count": len(product_rows),
        "shop_count": len(shop_rows),
        "reports": reports,
    }


def import_findniche_my_all_categories(
    conn,
    capture_date: str | None = None,
    limit_products_per_category: int = 50,
    limit_shops_per_category: int = 30,
) -> dict:
    chosen_date = capture_date or datetime.now(TZ_UTC8).date().isoformat()
    cleanup_existing_findniche_rows(conn, chosen_date)

    root_trending_html = fetch_html(TRENDING_URL)
    root_shops_html = fetch_html(TOP_SELLERS_URL)
    trending_paths = discover_trending_category_paths(root_trending_html)
    seller_paths = discover_top_seller_category_paths(root_shops_html)

    all_product_rows = []
    for path in trending_paths:
        url = f"{BASE_URL}{path}"
        html = fetch_html(url)
        slug = derive_slug_from_findniche_trending_path(path)
        (RAW_DIR / f"{slug}_trending.html").write_text(html, encoding="utf-8")
        rows = parse_trending_products(html, chosen_date, limit_products_per_category, fallback_category_slug=slug)
        all_product_rows.extend(rows)

    all_shop_rows = []
    for path in seller_paths:
        url = f"{BASE_URL}{path}"
        html = fetch_html(url)
        slug = derive_slug_from_findniche_top_seller_path(path)
        (RAW_DIR / f"{slug}_top_sellers.html").write_text(html, encoding="utf-8")
        rows = parse_top_shops(html, chosen_date, limit_shops_per_category, fallback_category_slug=slug)
        all_shop_rows.extend(rows)

    insert_product_rows(conn, all_product_rows)
    insert_shop_rows(conn, all_shop_rows)
    conn.commit()

    reports = export_category_capture_reports(conn, capture_date=chosen_date)
    return {
        "capture_date": chosen_date,
        "product_count": len(all_product_rows),
        "shop_count": len(all_shop_rows),
        "category_count_products": len({row["broad_category_slug"] for row in all_product_rows}),
        "category_count_shops": len({row["broad_category_slug"] for row in all_shop_rows}),
        "reports": reports,
    }


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=60, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def parse_trending_products(html: str, capture_date: str, limit_products: int, fallback_category_slug: str | None = None) -> list[dict]:
    objects = extract_rank_objects(
        html,
        id_key="product_id",
        required_keys={"rank", "title", "product_id", "preview_image_url"},
    )
    category_name = extract_current_category_name(html) or "Unknown"
    category_slug = fallback_category_slug or guess_category_slug_from_name(category_name)

    rows = []
    for obj in objects[:limit_products]:
        product_id = clean(str(obj.get("product_id", "")))
        title = clean(str(obj.get("title", "")))
        if not product_id or not title:
            continue
        price = parse_money(obj.get("price"))
        sold_count = parse_compact_count(obj.get("order_count"))
        week_order = parse_compact_count(obj.get("week_order"))
        gmv_value = parse_money(obj.get("gmv_count_long"))
        preview_image = clean(str(obj.get("preview_image_url", "")))
        notes = f"source=findniche_trending; week_order={week_order}; gmv={gmv_value}; image={preview_image}"
        rows.append(
            {
                "capture_date": capture_date,
                "broad_category_slug": category_slug,
                "sub_category": "",
                "micro_niche": "",
                "keyword": category_name,
                "rank": to_int(obj.get("rank")),
                "shop_name": "",
                "product_title": title,
                "price": price,
                "currency": "MYR",
                "sold_count": sold_count,
                "review_count": 0,
                "rating": 0,
                "product_url": f"https://shop.tiktok.com/view/product/{product_id}?region=MY&locale=en-MY",
                "shop_url": "",
                "video_flag": 0,
                "live_flag": 0,
                "notes": notes,
            }
        )
    return rows


def parse_top_shops(html: str, capture_date: str, limit_shops: int, fallback_category_slug: str | None = None) -> list[dict]:
    objects = extract_rank_objects(
        html,
        id_key="store_id",
        required_keys={"rank", "title", "store_id"},
    )
    category_name = extract_current_category_name(html) or "Unknown"
    category_slug = fallback_category_slug or guess_category_slug_from_name(category_name)

    rows = []
    for obj in objects[:limit_shops]:
        store_id = clean(str(obj.get("store_id", "")))
        title = clean(str(obj.get("title", "")))
        if not store_id or not title:
            continue
        rows.append(
            {
                "capture_date": capture_date,
                "broad_category_slug": category_slug,
                "shop_name": title,
                "shop_url": f"https://shop.tiktok.com/store/{store_id}",
                "category_focus": category_name,
                "shop_rating": parse_rating(obj.get("rating")),
                "product_count": to_int(obj.get("product_cnt")),
                "hero_products": "",
                "price_band": "",
                "content_style": "",
                "live_intensity": "",
                "notes": "source=findniche_top_sellers; week_gmv={}; total_orders={}; total_gmv={}".format(
                    clean(str(obj.get("week_gmv_cnt_long", ""))),
                    clean(str(obj.get("store_order_cnt", ""))),
                    clean(str(obj.get("store_gmv_cnt_long", ""))),
                ),
            }
        )
    return rows


def insert_product_rows(conn, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO category_product_samples (
            capture_date, broad_category_slug, sub_category, micro_niche, keyword, rank,
            shop_name, product_title, price, currency, sold_count, review_count, rating,
            product_url, shop_url, video_flag, live_flag, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["capture_date"],
                row["broad_category_slug"],
                row["sub_category"],
                row["micro_niche"],
                row["keyword"],
                row["rank"],
                row["shop_name"],
                row["product_title"],
                row["price"],
                row["currency"],
                row["sold_count"],
                row["review_count"],
                row["rating"],
                row["product_url"],
                row["shop_url"],
                row["video_flag"],
                row["live_flag"],
                row["notes"],
            )
            for row in rows
        ],
    )


def insert_shop_rows(conn, rows: list[dict]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO category_shop_samples (
            capture_date, broad_category_slug, shop_name, shop_url, category_focus,
            shop_rating, product_count, hero_products, price_band, content_style,
            live_intensity, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["capture_date"],
                row["broad_category_slug"],
                row["shop_name"],
                row["shop_url"],
                row["category_focus"],
                row["shop_rating"],
                row["product_count"],
                row["hero_products"],
                row["price_band"],
                row["content_style"],
                row["live_intensity"],
                row["notes"],
            )
            for row in rows
        ],
    )


def extract_current_category_name(html: str) -> str:
    match = re.search(r'"current_category":\d+,"current_country":\d+,"category_nav":\[.*?\],"country_nav":\[.*?\],"products":\[.*?\],"current_url":\d+,"file_name":\d+,"update_date":\d+,"update_year":\d+,"hot_categories":', html, re.S)
    if not match:
        title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        return clean(title_match.group(1)) if title_match else ""
    if "trending-products-my" in html:
        return "All Categories"
    return "All Categories"


def discover_trending_category_paths(html: str) -> list[str]:
    paths = sorted(set(re.findall(r"/tiktok/trending-[a-z0-9\-]+-products-my", html)))
    return paths


def discover_top_seller_category_paths(html: str) -> list[str]:
    paths = sorted(set(re.findall(r"/tiktok/top-sellers-[a-z0-9\-]+-my", html)))
    skip = {
        "/tiktok/top-sellers-my",
    }
    return [path for path in paths if path not in skip]


def derive_slug_from_findniche_trending_path(path: str) -> str:
    match = re.search(r"/tiktok/trending-(.*?)-products-my", path)
    raw = match.group(1) if match else path
    return normalize_findniche_slug(raw)


def derive_slug_from_findniche_top_seller_path(path: str) -> str:
    match = re.search(r"/tiktok/top-sellers-(.*?)-my", path)
    raw = match.group(1) if match else path
    return normalize_findniche_slug(raw)


def normalize_findniche_slug(raw: str) -> str:
    mapping = {
        "automotive-and-motorcycle": "automotive",
        "baby-and-maternity": "baby-maternity",
        "beauty-and-personal-care": "beauty-personal-care",
        "books-magazines-and-audio": "books-audio",
        "collectibles": "collectibles",
        "computers-and-office-equipment": "computers-office",
        "fashion-accessories": "fashion-accessories",
        "food-and-beverages": "food-beverages",
        "furniture": "furniture",
        "health": "health",
        "home-improvement": "home-improvement",
        "home-supplies": "home-supplies",
        "household-appliances": "appliances",
        "jewelry-accessories-and-derivatives": "jewelry-accessories",
        "kids-fashion": "kids-fashion",
        "kitchenware": "kitchenware",
        "luggage-and-bags": "bags",
        "menswear-and-underwear": "menswear",
        "muslim-fashion": "muslim-fashion",
        "pet-supplies": "pet-supplies",
        "phones-and-electronics": "phones-electronics",
        "shoes": "shoes",
        "sports-and-outdoor": "sports-outdoors",
        "textiles-and-soft-furnishings": "textiles",
        "tools-and-hardware": "tools-hardware",
        "toys-and-hobbies": "toys-hobbies",
        "womenswear-and-underwear": "womenswear",
    }
    return mapping.get(raw, raw)


def extract_rank_objects(html: str, id_key: str, required_keys: set[str]) -> list[dict]:
    data_blob = extract_nuxt_data_blob(html)
    ref_array = json.loads(data_blob)
    objects = []
    decoder = json.JSONDecoder()
    idx = 0
    while True:
        idx = data_blob.find('{"rank":', idx)
        if idx == -1:
            break
        try:
            obj, end = decoder.raw_decode(data_blob[idx:])
        except json.JSONDecodeError:
            idx += 7
            continue
        if isinstance(obj, dict) and id_key in obj and required_keys.issubset(set(obj.keys())):
            resolved = resolve_value(obj, ref_array)
            if isinstance(resolved, dict) and id_key in resolved:
                objects.append(resolved)
        idx += end
    return objects


def extract_nuxt_data_blob(html: str) -> str:
    match = re.search(r'<script type="application/json" data-nuxt-data="nuxt-app"[^>]*>(.*?)</script>', html, re.S)
    if match:
        return match.group(1)
    match = re.search(r'<script[^>]*>(\[\[.*\])</script>', html, re.S)
    if match:
        return match.group(1)
    raise RuntimeError("Could not locate FindNiche data blob.")


def resolve_value(value, ref_array):
    if isinstance(value, int) and 0 <= value < len(ref_array):
        target = ref_array[value]
        if isinstance(target, dict):
            return {key: resolve_value(item, ref_array) for key, item in target.items()}
        if isinstance(target, list):
            return [resolve_value(item, ref_array) for item in target]
        return target
    if isinstance(value, dict):
        return {key: resolve_value(item, ref_array) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, ref_array) for item in value]
    return value


def cleanup_existing_findniche_rows(conn, capture_date: str) -> None:
    conn.execute(
        "DELETE FROM category_product_samples WHERE capture_date = ? AND notes LIKE 'source=findniche_%'",
        (capture_date,),
    )
    conn.execute(
        "DELETE FROM category_shop_samples WHERE capture_date = ? AND notes LIKE 'source=findniche_%'",
        (capture_date,),
    )
    conn.commit()


def guess_category_slug_from_name(name: str) -> str:
    lookup = {
        "Womenswear & Underwear": "womenswear",
        "Menswear & Underwear": "menswear",
        "Kids' Fashion": "kids-fashion",
        "Muslim Fashion": "muslim-fashion",
        "Shoes": "shoes",
        "Luggage & Bags": "bags",
        "Fashion Accessories": "fashion-accessories",
        "Sports & Outdoor": "sports-outdoors",
        "Home Supplies": "home-supplies",
        "Kitchenware": "kitchenware",
        "Textiles & Soft Furnishings": "textiles",
        "Household Appliances": "appliances",
        "Beauty & Personal Care": "beauty-personal-care",
        "Computers & Office Equipment": "computers-office",
        "Phones & Electronics": "phones-electronics",
        "Pet Supplies": "pet-supplies",
        "Baby & Maternity": "baby-maternity",
        "Toys & Hobbies": "toys-hobbies",
        "Furniture": "furniture",
        "Tools & Hardware": "tools-hardware",
        "Home Improvement": "home-improvement",
        "Automotive & Motorcycle": "automotive",
        "Food & Beverages": "food-beverages",
        "Health": "health",
        "Books, Magazines & Audio": "books-audio",
        "Jewelry Accessories & Derivatives": "jewelry-accessories",
        "Collectibles": "collectibles",
        "All Categories": "all-categories",
    }
    return lookup.get(name, slugify(name))


def parse_compact_count(value: object) -> int:
    text = clean(str(value))
    if not text:
        return 0
    text = text.replace(",", "").replace(" ", "")
    multiplier = 1
    if text.lower().endswith("k"):
        multiplier = 1_000
        text = text[:-1]
    elif text.lower().endswith("m"):
        multiplier = 1_000_000
        text = text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def parse_money(value: object) -> float:
    text = clean(str(value))
    if not text:
        return 0.0
    text = text.replace("RM", "").replace(",", "").strip()
    multiplier = 1.0
    if text.lower().endswith("k"):
        multiplier = 1_000.0
        text = text[:-1]
    elif text.lower().endswith("m"):
        multiplier = 1_000_000.0
        text = text[:-1]
    try:
        return round(float(text) * multiplier, 2)
    except ValueError:
        return 0.0


def parse_rating(value: object) -> float:
    text = clean(str(value))
    if not text:
        return 0.0
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def to_int(value: object) -> int:
    text = clean(str(value))
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def slugify(text: str) -> str:
    text = clean(text).lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def clean(text: str) -> str:
    return str(text or "").strip()
