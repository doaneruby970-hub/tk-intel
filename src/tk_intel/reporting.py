import csv
from pathlib import Path

from .db import latest_score_run_id
from .scoring import category_summary, score_rows
from .settings import REPORTS_DIR


def export_latest_reports(conn, output_dir: Path | str = REPORTS_DIR, run_id: str | None = None) -> tuple[Path, Path]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    current_run_id = run_id or latest_score_run_id(conn)
    if not current_run_id:
        raise RuntimeError("No score run found. Run scoring first.")

    product_rows = score_rows(conn, current_run_id)
    category_rows = category_summary(conn, current_run_id)

    csv_path = target_dir / "latest_product_scores.csv"
    md_path = target_dir / "latest_report.md"

    write_product_csv(csv_path, product_rows)
    write_markdown_report(md_path, current_run_id, category_rows, product_rows)
    return csv_path, md_path


def write_product_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "category_slug",
        "title",
        "keyword",
        "shop_name",
        "latest_price",
        "sold_count",
        "sold_delta",
        "review_count",
        "review_delta",
        "rating",
        "demand_score",
        "growth_score",
        "competition_score",
        "margin_proxy_score",
        "risk_score",
        "opportunity_score",
        "opportunity_band",
        "rationale",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_report(path: Path, run_id: str, category_rows: list[dict], product_rows: list[dict]) -> None:
    top_categories = category_rows[:10]
    top_products = product_rows[:15]
    crowded = [
        row
        for row in product_rows
        if float(row["competition_score"]) >= 70 and float(row["opportunity_score"]) < 55
    ][:10]

    lines = [
        f"# TK Product Intelligence Report",
        "",
        f"- run_id: `{run_id}`",
        f"- categories scored: `{len(category_rows)}`",
        f"- products scored: `{len(product_rows)}`",
        "",
        "## Category ranking",
        "",
        "| category | tier | products | avg opportunity | avg growth | avg competition | avg price |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in top_categories:
        lines.append(
            "| {category_name} | {priority_tier} | {product_count} | {avg_opportunity_score} | {avg_growth_score} | {avg_competition_score} | {avg_price} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Top product opportunities",
            "",
            "| category | title | keyword | price | sold | sold delta | score | band | note |",
            "|---|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in top_products:
        lines.append(
            "| {category_slug} | {title} | {keyword} | {latest_price} | {sold_count} | {sold_delta} | {opportunity_score} | {opportunity_band} | {rationale} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Crowded watchlist",
            "",
            "| category | title | competition | risk | score | note |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in crowded:
        lines.append(
            "| {category_slug} | {title} | {competition_score} | {risk_score} | {opportunity_score} | {rationale} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## How to use this report",
            "",
            "1. Start from category ranking, not product ranking.",
            "2. Pick 3-5 categories with better average opportunity and still-manageable competition.",
            "3. Only then deep-track more products and suppliers inside those categories.",
            "4. Treat low-price, fast-growth, medium-competition products as testing candidates first.",
        ]
    )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
