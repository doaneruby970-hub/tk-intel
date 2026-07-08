import asyncio
import csv
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from .db import upsert_product_snapshot
from .importers import clean


DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def scrape_urls_to_db(
    conn,
    input_csv: Path | str,
    region: str = "MY",
    locale: str = "en-MY",
    headless: bool = True,
    delay_ms: int = 4500,
) -> int:
    rows = load_product_url_rows(input_csv)
    if not rows:
        return 0

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(user_agent=DESKTOP_UA, locale=locale)
        page = await context.new_page()
        imported = 0
        for row in rows:
            record = await scrape_single_product(
                page=page,
                product_url=row["product_url"],
                category_slug=row["category_slug"],
                keyword=row["keyword"],
                region=region,
                delay_ms=delay_ms,
            )
            upsert_product_snapshot(conn, record)
            imported += 1
        await context.close()
        await browser.close()
    return imported


def load_product_url_rows(input_csv: Path | str) -> list[dict]:
    path = Path(input_csv)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {
                "product_url": clean(row.get("product_url")),
                "category_slug": clean(row.get("category_slug")),
                "keyword": clean(row.get("keyword")),
                "notes": clean(row.get("notes")),
            }
            for row in reader
            if clean(row.get("product_url"))
        ]
    return rows


async def scrape_single_product(
    page,
    product_url: str,
    category_slug: str,
    keyword: str,
    region: str,
    delay_ms: int = 4500,
) -> dict:
    await page.goto(product_url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(delay_ms)

    html = await page.content()
    title = await page.title()
    body_text = await safe_body_text(page)
    next_data = await safe_window_value(page, "__NEXT_DATA__")
    sigi_state = await safe_window_value(page, "SIGI_STATE")

    product_id = extract_product_id(product_url, html)
    shop_name = first_non_empty(
        find_value(next_data, {"shop_name", "seller_name", "shopName"}),
        find_value(sigi_state, {"shop_name", "seller_name", "shopName"}),
        regex_group(r'"shop_name"\s*:\s*"([^"]+)"', html),
        regex_group(r'"seller_name"\s*:\s*"([^"]+)"', html),
    )
    product_title = first_non_empty(
        find_value(next_data, {"title", "product_name", "name"}),
        find_value(sigi_state, {"title", "product_name", "name"}),
        regex_group(r'"product_name"\s*:\s*"([^"]+)"', html),
        regex_group(r'<title>([^<]+)</title>', html),
        title,
    )

    price = first_float(
        find_value(next_data, {"sale_price", "price"}),
        find_value(sigi_state, {"sale_price", "price"}),
        regex_group(r'"sale_price"\s*:\s*"?([\d.]+)', html),
        regex_group(r'"price"\s*:\s*"?([\d.]+)', html),
        parse_first_currency_number(body_text),
    )
    original_price = optional_float(
        first_non_empty(
            find_value(next_data, {"origin_price", "original_price", "market_price"}),
            find_value(sigi_state, {"origin_price", "original_price", "market_price"}),
            regex_group(r'"original_price"\s*:\s*"?([\d.]+)', html),
        )
    )
    sold_count = first_int(
        find_value(next_data, {"product_sold_count", "sold_count", "sales"}),
        find_value(sigi_state, {"product_sold_count", "sold_count", "sales"}),
        regex_group(r'"product_sold_count"\s*:\s*"?([\d.]+)', html),
        parse_sold_count(body_text),
    )
    review_count = first_int(
        find_value(next_data, {"review_count", "comment_count"}),
        find_value(sigi_state, {"review_count", "comment_count"}),
        regex_group(r'"review_count"\s*:\s*"?([\d.]+)', html),
    )
    rating = first_float(
        find_value(next_data, {"rating", "average_rating"}),
        find_value(sigi_state, {"rating", "average_rating"}),
        regex_group(r'"average_rating"\s*:\s*"?([\d.]+)', html),
    )

    captured_at = datetime.now(timezone(timedelta(hours=8))).isoformat()
    return {
        "product_id": product_id,
        "category_slug": category_slug,
        "keyword": keyword,
        "title": clean(product_title).split("|")[0].strip(),
        "shop_name": clean(shop_name),
        "product_url": product_url,
        "price": price,
        "original_price": original_price,
        "currency": "MYR",
        "sold_count": sold_count,
        "review_count": review_count,
        "rating": rating,
        "creator_count": 0,
        "video_count": 0,
        "competitor_count": 0,
        "captured_at": captured_at,
        "source_type": "public_playwright",
        "stock_status": "",
        "raw_path": "",
        "notes": "",
        "region": region,
    }


async def safe_window_value(page, key: str) -> Any:
    script = f"() => window.{key} || null"
    try:
        return await page.evaluate(script)
    except Exception:
        return None


async def safe_body_text(page) -> str:
    try:
        return await page.locator("body").inner_text()
    except Exception:
        return ""


def extract_product_id(product_url: str, html: str) -> str:
    match = re.search(r"/product/(\d+)", product_url)
    if match:
        return match.group(1)
    match = re.search(r'"product_id"\s*:\s*"?(\\?\d+)', html)
    if match:
        return match.group(1).replace("\\", "")
    return ""


def find_value(payload: Any, candidate_keys: set[str]) -> Any:
    if payload is None:
        return None
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in candidate_keys and value not in (None, "", [], {}):
                return value
            found = find_value(value, candidate_keys)
            if found not in (None, "", [], {}):
                return found
    if isinstance(payload, list):
        for value in payload:
            found = find_value(value, candidate_keys)
            if found not in (None, "", [], {}):
                return found
    return None


def parse_sold_count(text: str) -> int:
    match = re.search(r"([\d,.]+)\s*(k|m)?\s*sold", text, re.IGNORECASE)
    if not match:
        return 0
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    if suffix == "k":
        number *= 1000
    elif suffix == "m":
        number *= 1_000_000
    return int(number)


def parse_first_currency_number(text: str) -> float:
    match = re.search(r"(?:rm|myr)\s*([\d,.]+)", text, re.IGNORECASE)
    if not match:
        return 0.0
    return float(match.group(1).replace(",", ""))


def regex_group(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return "" if match is None else match.group(1)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def first_float(*values: Any) -> float:
    for value in values:
        try:
            if value not in (None, "", [], {}):
                return float(str(value).replace(",", ""))
        except ValueError:
            continue
    return 0.0


def optional_float(value: Any) -> float | None:
    if value in (None, "", [], {}):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def first_int(*values: Any) -> int:
    for value in values:
        try:
            if value not in (None, "", [], {}):
                return int(float(str(value).replace(",", "")))
        except ValueError:
            continue
    return 0
