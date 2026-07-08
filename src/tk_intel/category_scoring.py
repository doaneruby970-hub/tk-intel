import csv
import re
from pathlib import Path

from .db import fetch_rows
from .settings import REPORTS_DIR


def score_categories_from_capture(conn, capture_date: str | None = None, output_dir: Path | str = REPORTS_DIR) -> dict[str, Path]:
    selected_date = capture_date or latest_capture_date(conn)
    if not selected_date:
        raise RuntimeError("No category capture data found.")

    category_rows = build_category_scores(conn, selected_date)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "latest_category_scores.csv"
    md_path = output_root / "latest_category_scores.md"

    write_csv(csv_path, category_rows)
    write_markdown(md_path, selected_date, category_rows)

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


def build_category_scores(conn, capture_date: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            c.category_slug,
            c.category_name,
            c.priority_tier,
            c.content_fit,
            c.logistics_risk,
            cps.product_title,
            cps.price,
            cps.sold_count,
            cps.shop_name,
            cps.product_url
        FROM category_product_samples cps
        JOIN categories c ON c.category_slug = cps.broad_category_slug
        WHERE cps.capture_date = ?
        """,
        (capture_date,),
    )

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(str(row["category_slug"]), []).append(row)

    scored = []
    for slug, items in grouped.items():
        category_name = str(items[0]["category_name"])
        priority_tier = str(items[0]["priority_tier"])
        content_fit = to_float(items[0]["content_fit"])
        logistics_risk = to_float(items[0]["logistics_risk"])

        prices = [to_float(item["price"]) for item in items if to_float(item["price"]) > 0]
        sold_counts = [to_float(item["sold_count"]) for item in items if to_float(item["sold_count"]) > 0]
        shops = [clean(item["shop_name"]) for item in items if clean(item["shop_name"])]
        unique_products = len({clean(item["product_url"]) or clean(item["product_title"]) for item in items})
        unique_shops = len(set(shops))

        avg_price = average(prices)
        median_price = median(prices)
        avg_sold = average(sold_counts)
        median_sold = median(sold_counts)
        top10_share = top_share(sold_counts, 10)
        shop_concentration = top_shop_share(shops)
        shop_metrics = shop_metrics_for_category(conn, slug, capture_date)
        cr3_share = concentration_share(shop_metrics, 3)
        cr5_share = concentration_share(shop_metrics, 5)

        demand_score = round(
            0.55 * sold_score(avg_sold, median_sold)
            + 0.20 * coverage_score(unique_products)
            + 0.25 * content_fit_score(content_fit),
            2,
        )
        competition_score = round(
            0.50 * shop_count_score(unique_shops)
            + 0.30 * concentration_penalty(shop_concentration)
            + 0.10 * sample_density_score(unique_products)
            + 0.10 * concentration_share_penalty(cr3_share, cr5_share),
            2,
        )
        price_band_score = round(price_fit_score(avg_price, median_price), 2)
        ops_risk_score = round(
            0.65 * logistics_penalty(logistics_risk)
            + 0.35 * price_extreme_penalty(avg_price),
            2,
        )

        category_score = round(
            0.35 * demand_score
            + 0.25 * price_band_score
            + 0.20 * (100 - competition_score)
            + 0.20 * (100 - ops_risk_score),
            2,
        )
        recommendation = classify_category(category_score, competition_score, ops_risk_score)
        rationale = build_rationale(
            demand_score=demand_score,
            competition_score=competition_score,
            price_band_score=price_band_score,
            ops_risk_score=ops_risk_score,
            avg_price=avg_price,
            unique_shops=unique_shops,
            shop_concentration=shop_concentration,
        )

        scored.append(
            {
                "capture_date": capture_date,
                "category_slug": slug,
                "category_name": category_name,
                "priority_tier": priority_tier,
                "sample_count": len(items),
                "unique_products": unique_products,
                "unique_shops": unique_shops,
                "avg_price": round(avg_price, 2),
                "median_price": round(median_price, 2),
                "avg_sold_count": round(avg_sold, 2),
                "median_sold_count": round(median_sold, 2),
                "top10_sold_share_pct": round(top10_share, 2),
                "top_shop_share_pct": round(shop_concentration, 2),
                "cr3_share_pct": round(cr3_share, 2),
                "cr5_share_pct": round(cr5_share, 2),
                "demand_score": demand_score,
                "competition_score": competition_score,
                "price_band_score": price_band_score,
                "ops_risk_score": ops_risk_score,
                "category_score": category_score,
                "recommendation": recommendation,
                "rationale": rationale,
            }
        )

    scored.sort(key=lambda item: (-item["category_score"], item["competition_score"], item["category_slug"]))
    return scored


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, capture_date: str, rows: list[dict]) -> None:
    prioritize = [row for row in rows if row["recommendation"] == "优先做"]
    watch = [row for row in rows if row["recommendation"] == "先观察"]
    avoid = [row for row in rows if row["recommendation"] == "暂不建议"]

    lines = [
        "# Category Scoring",
        "",
        f"- capture_date: `{capture_date}`",
        f"- categories scored: `{len(rows)}`",
        "",
        "## Overall ranking",
        "",
        "| category | score | demand | competition | cr3 | cr5 | price band | ops risk | recommendation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {category_name} | {category_score} | {demand_score} | {competition_score} | {cr3_share_pct} | {cr5_share_pct} | {price_band_score} | {ops_risk_score} | {recommendation} |".format(
                **row
            )
        )

    if prioritize:
        lines.extend(["", "## 优先做", "", "| category | score | note |", "|---|---:|---|"])
        for row in prioritize:
            lines.append("| {category_name} | {category_score} | {rationale} |".format(**row))

    if watch:
        lines.extend(["", "## 先观察", "", "| category | score | note |", "|---|---:|---|"])
        for row in watch:
            lines.append("| {category_name} | {category_score} | {rationale} |".format(**row))

    if avoid:
        lines.extend(["", "## 暂不建议", "", "| category | score | note |", "|---|---:|---|"])
        for row in avoid:
            lines.append("| {category_name} | {category_score} | {rationale} |".format(**row))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sold_score(avg_sold: float, median_sold: float) -> float:
    return min(100.0, 0.6 * scale(avg_sold, 150000.0) + 0.4 * scale(median_sold, 100000.0))


def coverage_score(unique_products: int) -> float:
    return min(100.0, unique_products / 100.0 * 100.0)


def content_fit_score(content_fit: float) -> float:
    return min(100.0, max(0.0, content_fit / 5.0 * 100.0))


def shop_count_score(unique_shops: int) -> float:
    return min(100.0, unique_shops / 60.0 * 100.0)


def concentration_penalty(top_shop_share_pct: float) -> float:
    return min(100.0, top_shop_share_pct)


def sample_density_score(unique_products: int) -> float:
    return min(100.0, unique_products / 80.0 * 100.0)


def concentration_share_penalty(cr3_share: float, cr5_share: float) -> float:
    return min(100.0, 0.6 * cr3_share + 0.4 * cr5_share)


def price_fit_score(avg_price: float, median_price: float) -> float:
    base = (avg_price + median_price) / 2.0
    if 5 <= base <= 80:
        return 88.0
    if 80 < base <= 150:
        return 68.0
    if 150 < base <= 300:
        return 45.0
    if 1 <= base < 5:
        return 40.0
    return 20.0


def logistics_penalty(logistics_risk: float) -> float:
    return min(100.0, logistics_risk / 5.0 * 100.0)


def price_extreme_penalty(avg_price: float) -> float:
    if avg_price <= 0:
        return 80.0
    if avg_price < 2:
        return 85.0
    if avg_price > 300:
        return 70.0
    if avg_price > 150:
        return 45.0
    return 20.0


def classify_category(category_score: float, competition_score: float, ops_risk_score: float) -> str:
    if category_score >= 65 and competition_score <= 70 and ops_risk_score <= 65:
        return "优先做"
    if category_score >= 48:
        return "先观察"
    return "暂不建议"


def build_rationale(
    demand_score: float,
    competition_score: float,
    price_band_score: float,
    ops_risk_score: float,
    avg_price: float,
    unique_shops: int,
    shop_concentration: float,
) -> str:
    parts = []
    if demand_score >= 70:
        parts.append("需求强")
    if competition_score >= 70:
        parts.append("竞争偏挤")
    elif competition_score <= 40:
        parts.append("竞争可控")
    if price_band_score >= 80:
        parts.append("价格带适合冲动单")
    elif avg_price > 150:
        parts.append("客单偏高")
    if ops_risk_score >= 60:
        parts.append("经营风险偏高")
    if unique_shops <= 5:
        parts.append("店铺分布偏集中")
    if shop_concentration >= 60:
        parts.append("头部集中度高")
    return "；".join(parts) if parts else "信号中性"


def average(values: list[float]) -> float:
    valid = [value for value in values if value is not None]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def median(values: list[float]) -> float:
    valid = sorted([value for value in values if value is not None])
    if not valid:
        return 0.0
    mid = len(valid) // 2
    if len(valid) % 2 == 1:
        return valid[mid]
    return (valid[mid - 1] + valid[mid]) / 2.0


def top_share(values: list[float], top_n: int) -> float:
    valid = sorted([value for value in values if value is not None], reverse=True)
    if not valid:
        return 0.0
    total = sum(valid)
    if total <= 0:
        return 0.0
    return sum(valid[:top_n]) / total * 100.0


def top_shop_share(shops: list[str]) -> float:
    if not shops:
        return 100.0
    counts: dict[str, int] = {}
    for shop in shops:
        counts[shop] = counts.get(shop, 0) + 1
    top = max(counts.values())
    return top / len(shops) * 100.0


def scale(value: float, cap: float) -> float:
    if cap <= 0:
        return 0.0
    return min(100.0, max(0.0, value / cap * 100.0))


def to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def shop_metrics_for_category(conn, category_slug: str, capture_date: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT shop_name, shop_url, notes
        FROM category_shop_samples
        WHERE broad_category_slug = ? AND capture_date = ?
        """,
        (category_slug, capture_date),
    )
    metrics = []
    for row in rows:
        note = clean(row["notes"])
        week_gmv = parse_metric(note, "week_gmv")
        total_gmv = parse_metric(note, "total_gmv")
        total_orders = parse_metric(note, "total_orders")
        metrics.append(
            {
                "shop_name": clean(row["shop_name"]),
                "shop_url": clean(row["shop_url"]),
                "week_gmv": week_gmv,
                "total_gmv": total_gmv,
                "total_orders": total_orders,
            }
        )
    return metrics


def concentration_share(rows: list[dict], top_n: int) -> float:
    if not rows:
        return 100.0
    values = sorted([row["total_gmv"] for row in rows if row["total_gmv"] > 0], reverse=True)
    if not values:
        values = sorted([row["week_gmv"] for row in rows if row["week_gmv"] > 0], reverse=True)
    total = sum(values)
    if total <= 0:
        return 0.0
    return sum(values[:top_n]) / total * 100.0


def parse_metric(text: str, field: str) -> float:
    match = re.search(rf"{re.escape(field)}=([^;]+)", text or "")
    if not match:
        return 0.0
    value = match.group(1).strip()
    return parse_compact(value)


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


def clean(value: object) -> str:
    return str(value or "").strip()
