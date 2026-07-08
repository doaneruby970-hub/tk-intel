import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from .db import fetch_rows


@dataclass
class ProductMetric:
    product_key: str
    category_slug: str
    title: str
    keyword: str
    shop_name: str
    latest_captured_at: str
    latest_price: float
    sold_count: int
    sold_delta: int
    review_count: int
    review_delta: int
    rating: float
    creator_count: int
    video_count: int
    competitor_count: int


def run_scoring(conn, region: str = "MY", notes: str = "") -> str:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    conn.execute(
        "INSERT INTO score_runs (run_id, created_at, region, notes) VALUES (?, ?, ?, ?)",
        (run_id, datetime.now(timezone.utc).isoformat(), region, notes),
    )

    metrics = latest_product_metrics(conn, region=region)
    rows_to_insert = []
    for item in metrics:
        score = score_product(item)
        rows_to_insert.append(
            (
                run_id,
                item.product_key,
                item.category_slug,
                item.title,
                item.keyword,
                item.shop_name,
                item.latest_captured_at,
                item.latest_price,
                item.sold_count,
                item.sold_delta,
                item.review_count,
                item.review_delta,
                item.rating,
                score["demand_score"],
                score["growth_score"],
                score["competition_score"],
                score["margin_proxy_score"],
                score["risk_score"],
                score["opportunity_score"],
                score["opportunity_band"],
                score["rationale"],
            )
        )

    conn.executemany(
        """
        INSERT OR REPLACE INTO product_scores (
            run_id, product_key, category_slug, title, keyword, shop_name, latest_captured_at,
            latest_price, sold_count, sold_delta, review_count, review_delta, rating,
            demand_score, growth_score, competition_score, margin_proxy_score, risk_score,
            opportunity_score, opportunity_band, rationale
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows_to_insert,
    )
    conn.commit()
    return run_id


def latest_product_metrics(conn, region: str = "MY") -> list[ProductMetric]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            p.product_key,
            p.category_slug,
            p.title,
            p.shop_name,
            s.captured_at,
            s.keyword,
            s.price,
            s.sold_count,
            s.review_count,
            s.rating,
            s.creator_count,
            s.video_count,
            s.competitor_count
        FROM products p
        JOIN product_snapshots s ON s.product_key = p.product_key
        WHERE p.region = ?
        ORDER BY p.product_key, s.captured_at DESC
        """,
        (region,),
    )

    grouped: dict[str, list] = defaultdict(list)
    for row in rows:
        grouped[str(row["product_key"])].append(row)

    results: list[ProductMetric] = []
    for product_key, snapshots in grouped.items():
        latest = snapshots[0]
        previous = snapshots[1] if len(snapshots) > 1 else None
        results.append(
            ProductMetric(
                product_key=product_key,
                category_slug=str(latest["category_slug"]),
                title=str(latest["title"]),
                keyword=str(latest["keyword"] or ""),
                shop_name=str(latest["shop_name"] or ""),
                latest_captured_at=str(latest["captured_at"]),
                latest_price=float(latest["price"] or 0),
                sold_count=int(latest["sold_count"] or 0),
                sold_delta=int(latest["sold_count"] or 0) - int(previous["sold_count"] or 0) if previous else 0,
                review_count=int(latest["review_count"] or 0),
                review_delta=int(latest["review_count"] or 0) - int(previous["review_count"] or 0) if previous else 0,
                rating=float(latest["rating"] or 0),
                creator_count=int(latest["creator_count"] or 0),
                video_count=int(latest["video_count"] or 0),
                competitor_count=int(latest["competitor_count"] or 0),
            )
        )
    return results


def score_product(item: ProductMetric) -> dict:
    demand_score = round(
        0.50 * log_scaled(item.sold_count, top=10000)
        + 0.20 * log_scaled(item.review_count, top=3000)
        + 0.30 * linear_rating_score(item.rating),
        2,
    )

    growth_score = round(
        0.65 * growth_to_score(item.sold_count, item.sold_delta)
        + 0.35 * growth_to_score(item.review_count, item.review_delta),
        2,
    )

    competition_score = round(
        0.50 * capped_scale(item.competitor_count, 80)
        + 0.30 * capped_scale(item.video_count, 250)
        + 0.20 * capped_scale(item.creator_count, 80),
        2,
    )

    margin_proxy_score = round(price_band_score(item.latest_price), 2)

    risk_score = round(
        0.55 * (100 - linear_rating_score(item.rating))
        + 0.20 * low_review_risk(item.review_count)
        + 0.25 * oversaturation_risk(item.video_count, item.competitor_count),
        2,
    )

    opportunity_score = round(
        0.30 * demand_score
        + 0.25 * growth_score
        + 0.20 * margin_proxy_score
        + 0.15 * (100 - competition_score)
        + 0.10 * (100 - risk_score),
        2,
    )

    band = opportunity_band(opportunity_score)
    rationale = build_rationale(
        demand_score=demand_score,
        growth_score=growth_score,
        competition_score=competition_score,
        margin_proxy_score=margin_proxy_score,
        risk_score=risk_score,
        sold_delta=item.sold_delta,
        review_delta=item.review_delta,
    )
    return {
        "demand_score": demand_score,
        "growth_score": growth_score,
        "competition_score": competition_score,
        "margin_proxy_score": margin_proxy_score,
        "risk_score": risk_score,
        "opportunity_score": opportunity_score,
        "opportunity_band": band,
        "rationale": rationale,
    }


def category_summary(conn, run_id: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            c.category_slug,
            c.category_name,
            c.priority_tier,
            COUNT(*) AS product_count,
            ROUND(AVG(ps.opportunity_score), 2) AS avg_opportunity_score,
            ROUND(AVG(ps.competition_score), 2) AS avg_competition_score,
            ROUND(AVG(ps.latest_price), 2) AS avg_price,
            ROUND(AVG(ps.growth_score), 2) AS avg_growth_score
        FROM product_scores ps
        JOIN categories c ON c.category_slug = ps.category_slug
        WHERE ps.run_id = ?
        GROUP BY c.category_slug, c.category_name, c.priority_tier
        ORDER BY avg_opportunity_score DESC, avg_growth_score DESC
        """,
        (run_id,),
    )
    return [dict(row) for row in rows]


def score_rows(conn, run_id: str) -> list[dict]:
    rows = fetch_rows(
        conn,
        """
        SELECT
            category_slug,
            title,
            keyword,
            shop_name,
            latest_price,
            sold_count,
            sold_delta,
            review_count,
            review_delta,
            rating,
            demand_score,
            growth_score,
            competition_score,
            margin_proxy_score,
            risk_score,
            opportunity_score,
            opportunity_band,
            rationale
        FROM product_scores
        WHERE run_id = ?
        ORDER BY opportunity_score DESC, growth_score DESC
        """,
        (run_id,),
    )
    return [dict(row) for row in rows]


def log_scaled(value: int, top: int) -> float:
    value = max(value, 0)
    top = max(top, 1)
    numerator = math.log10(value + 1)
    denominator = math.log10(top + 1)
    return min(100.0, 100.0 * numerator / denominator)


def linear_rating_score(rating: float) -> float:
    if rating <= 0:
        return 0
    return min(100.0, max(0.0, (rating / 5.0) * 100.0))


def growth_to_score(current: int, delta: int) -> float:
    if current <= 0 and delta <= 0:
        return 0.0
    baseline = max(current - delta, 1)
    growth_ratio = delta / baseline
    if growth_ratio <= -0.5:
        return 0.0
    if growth_ratio >= 1.5:
        return 100.0
    return max(0.0, min(100.0, (growth_ratio + 0.5) / 2.0 * 100.0))


def capped_scale(value: int, cap: int) -> float:
    return min(100.0, max(0.0, value / max(cap, 1) * 100.0))


def price_band_score(price: float) -> float:
    if 10 <= price <= 80:
        return 88.0
    if 80 < price <= 150:
        return 68.0
    if 5 <= price < 10:
        return 58.0
    if 150 < price <= 300:
        return 42.0
    return 25.0


def low_review_risk(review_count: int) -> float:
    if review_count >= 100:
        return 15.0
    if review_count >= 30:
        return 35.0
    return 70.0


def oversaturation_risk(video_count: int, competitor_count: int) -> float:
    return min(100.0, 0.45 * capped_scale(video_count, 250) + 0.55 * capped_scale(competitor_count, 80))


def opportunity_band(score: float) -> str:
    if score >= 70:
        return "prioritize testing"
    if score >= 55:
        return "keep watching"
    if score >= 40:
        return "cautious"
    return "crowded or weak"


def build_rationale(
    demand_score: float,
    growth_score: float,
    competition_score: float,
    margin_proxy_score: float,
    risk_score: float,
    sold_delta: int,
    review_delta: int,
) -> str:
    parts = []
    if growth_score >= 65 and sold_delta > 0:
        parts.append("sales momentum is strong")
    if demand_score >= 70:
        parts.append("base demand looks healthy")
    if competition_score >= 70:
        parts.append("competition is already crowded")
    if margin_proxy_score >= 80:
        parts.append("price band is favorable for impulse testing")
    if risk_score >= 60:
        parts.append("risk is elevated and needs manual validation")
    if review_delta > 0 and growth_score >= 45:
        parts.append("reviews are still accumulating")
    return "; ".join(parts) if parts else "signal is mixed and needs more snapshots"
