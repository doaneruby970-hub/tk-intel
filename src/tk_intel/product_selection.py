import csv
import math
import re
from pathlib import Path

from .db import fetch_rows
from .settings import REPORTS_DIR


def select_products_from_capture(
    conn,
    capture_date: str | None = None,
    min_category_score: float = 65.0,
    top_n_per_category: int = 8,
    output_dir: Path | str = REPORTS_DIR,
) -> dict[str, Path]:
    selected_date = capture_date or latest_capture_date(conn)
    if not selected_date:
        raise RuntimeError("No captured product data found.")

    category_scores = load_category_scores(selected_date)
    products = load_products(conn, selected_date)

    if not products:
        raise RuntimeError("No product samples available for selection.")

    max_week_order = max((item["week_order"] for item in products), default=1.0)
    max_sold = max((item["sold_count"] for item in products), default=1.0)
    max_gmv = max((item["gmv"] for item in products), default=1.0)

    candidates = []
    for item in products:
        category_score = category_scores.get(item["category_slug"], {}).get("category_score", 0.0)
        if category_score < min_category_score:
            continue
        week_order_score = log_scale(item["week_order"], max_week_order)
        sold_score = log_scale(item["sold_count"], max_sold)
        gmv_score = log_scale(item["gmv"], max_gmv)
        momentum_score = momentum_ratio_score(item["week_order"], item["sold_count"])
        price_score = price_fit_score(item["price"])
        product_score = round(
            0.30 * category_score
            + 0.25 * week_order_score
            + 0.15 * sold_score
            + 0.15 * gmv_score
            + 0.10 * momentum_score
            + 0.05 * price_score,
            2,
        )
        candidates.append(
            {
                "capture_date": selected_date,
                "category_slug": item["category_slug"],
                "category_name": category_scores.get(item["category_slug"], {}).get("category_name", item["category_slug"]),
                "category_score": round(category_score, 2),
                "product_score": product_score,
                "rank": item["rank"],
                "product_title": item["product_title"],
                "price": round(item["price"], 2),
                "sold_count": int(item["sold_count"]),
                "week_order": round(item["week_order"], 2),
                "gmv": round(item["gmv"], 2),
                "product_url": item["product_url"],
                "shop_name": item["shop_name"],
                "notes": item["notes"],
                "signal": product_signal(product_score, category_score, momentum_score, price_score),
            }
        )

    candidates.sort(key=lambda row: (-row["product_score"], -row["week_order"], row["category_slug"]))
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    csv_path = output_root / "latest_product_candidates.csv"
    md_path = output_root / "latest_product_candidates.md"

    write_csv(csv_path, candidates)
    write_markdown(md_path, selected_date, candidates, top_n_per_category)
    return {"csv_path": csv_path, "md_path": md_path}


def latest_capture_date(conn) -> str | None:
    row = conn.execute(
        """
        SELECT capture_date
        FROM category_product_samples
        ORDER BY capture_date DESC
        LIMIT 1
        """
    ).fetchone()
    return None if row is None else str(row[0])


def load_category_scores(capture_date: str) -> dict[str, dict]:
    path = REPORTS_DIR / "latest_category_scores.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out = {}
    for row in rows:
        if row.get("capture_date") != capture_date:
            continue
        slug = row.get("category_slug", "")
        out[slug] = {
            "category_name": row.get("category_name", slug),
            "category_score": to_float(row.get("category_score")),
            "recommendation": row.get("recommendation", ""),
        }
    return out


def load_products(conn, capture_date: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            broad_category_slug,
            rank,
            shop_name,
            product_title,
            price,
            sold_count,
            product_url,
            notes
        FROM category_product_samples
        WHERE capture_date = ?
        """,
        (capture_date,),
    )
    products = []
    for row in rows:
        note = clean(row["notes"])
        products.append(
            {
                "category_slug": clean(row["broad_category_slug"]),
                "rank": to_int(row["rank"]),
                "shop_name": clean(row["shop_name"]),
                "product_title": clean(row["product_title"]),
                "price": to_float(row["price"]),
                "sold_count": to_float(row["sold_count"]),
                "week_order": parse_metric(note, "week_order"),
                "gmv": parse_metric(note, "gmv"),
                "product_url": clean(row["product_url"]),
                "notes": note,
            }
        )
    return products


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, capture_date: str, rows: list[dict], top_n_per_category: int) -> None:
    lines = [
        "# Product Candidates",
        "",
        f"- capture_date: `{capture_date}`",
        f"- candidate rows: `{len(rows)}`",
        f"- top_n_per_category: `{top_n_per_category}`",
        "",
        "## Top candidates",
        "",
        "| category | product score | category score | product | price | sold | week order | signal |",
        "|---|---:|---:|---|---:|---:|---:|---|",
    ]
    for row in rows[:100]:
        lines.append(
            "| {category_name} | {product_score} | {category_score} | {product_title} | {price} | {sold_count} | {week_order} | {signal} |".format(
                **row
            )
        )

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["category_slug"], []).append(row)

    for slug, items in grouped.items():
        top_items = items[:top_n_per_category]
        lines.extend(
            [
                "",
                f"## {items[0]['category_name']}",
                "",
                "| product score | category score | product | price | sold | week order | gmv | signal |",
                "|---|---:|---|---:|---:|---:|---:|---|",
            ]
        )
        for row in top_items:
            lines.append(
                "| {product_score} | {category_score} | {product_title} | {price} | {sold_count} | {week_order} | {gmv} | {signal} |".format(
                    **row
                )
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def product_signal(product_score: float, category_score: float, momentum_score: float, price_score: float) -> str:
    if product_score >= 70 and category_score >= 65:
        return "test now"
    if product_score >= 55:
        return "watch"
    if momentum_score >= 60 and price_score >= 70:
        return "watch"
    return "skip"


def price_fit_score(price: float) -> float:
    if 5 <= price <= 80:
        return 100.0
    if 80 < price <= 150:
        return 70.0
    if 1 <= price < 5:
        return 55.0
    if 150 < price <= 300:
        return 35.0
    return 20.0


def momentum_ratio_score(week_order: float, sold_count: float) -> float:
    if sold_count <= 0:
        return 0.0
    ratio = week_order / sold_count
    if ratio <= 0:
        return 0.0
    return min(100.0, ratio * 1000.0)


def log_scale(value: float, max_value: float) -> float:
    if value <= 0 or max_value <= 0:
        return 0.0
    return min(100.0, math.log10(value + 1) / math.log10(max_value + 1) * 100.0)


def parse_metric(text: str, field: str) -> float:
    match = re.search(rf"{re.escape(field)}=([^;]+)", text or "")
    if not match:
        return 0.0
    return parse_compact(match.group(1))


def parse_compact(value: str) -> float:
    text = clean(value).replace(",", "").upper()
    if not text:
        return 0.0
    multiplier = 1.0
    if text.endswith("K"):
        multiplier = 1000.0
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1000000.0
        text = text[:-1]
    if text.startswith("RM"):
        text = text[2:]
    try:
        return float(text) * multiplier
    except ValueError:
        return 0.0


def to_int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def to_float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def clean(value: object) -> str:
    return str(value or "").strip()
