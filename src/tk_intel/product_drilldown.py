import csv
import re
from collections import defaultdict
from pathlib import Path

from .settings import CONFIG_DIR, REPORTS_DIR


TAXONOMY_PATH = CONFIG_DIR / "category_taxonomy_my.csv"
PRODUCT_CANDIDATES_PATH = REPORTS_DIR / "latest_product_candidates.csv"


def build_product_drilldown(
    product_candidates_csv: Path | str | None = PRODUCT_CANDIDATES_PATH,
    taxonomy_csv: Path | str = TAXONOMY_PATH,
    output_dir: Path | str = REPORTS_DIR,
) -> dict[str, Path]:
    candidates_path = Path(product_candidates_csv) if product_candidates_csv else PRODUCT_CANDIDATES_PATH
    candidates = read_csv(candidates_path)
    taxonomy = read_csv(taxonomy_csv)
    taxonomy_by_category = group_taxonomy(taxonomy)

    drilled_rows = []
    for row in candidates:
        matched = match_taxonomy(row["product_title"], row["category_slug"], taxonomy_by_category)
        drilled_rows.append(
            {
                **row,
                "sub_category": matched["sub_category"],
                "micro_niche": matched["micro_niche"],
                "match_score": matched["match_score"],
                "matched_keywords": matched["matched_keywords"],
                "fit_tier": matched["my_fit"],
                "selection_mode": matched["selection_mode"],
                "selection_note": matched["selection_note"],
            }
        )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    csv_path = output_root / "latest_product_drilldown.csv"
    md_path = output_root / "latest_product_drilldown.md"
    niche_csv_path = output_root / "latest_micro_niche_summary.csv"
    niche_md_path = output_root / "latest_micro_niche_summary.md"

    write_csv(csv_path, drilled_rows)
    write_markdown(md_path, drilled_rows)

    niche_rows = summarize_micro_niches(drilled_rows)
    write_csv(niche_csv_path, niche_rows)
    write_niche_markdown(niche_md_path, niche_rows, drilled_rows)

    return {
        "csv_path": csv_path,
        "md_path": md_path,
        "niche_csv_path": niche_csv_path,
        "niche_md_path": niche_md_path,
    }


def group_taxonomy(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["broad_category_slug"]].append(row)
    return grouped


def match_taxonomy(title: str, category_slug: str, taxonomy_by_category: dict[str, list[dict]]) -> dict:
    title_norm = normalize(title)
    best = {
        "sub_category": "",
        "micro_niche": "",
        "match_score": 0,
        "matched_keywords": "",
        "my_fit": "",
        "selection_mode": "",
        "selection_note": "",
    }
    for row in taxonomy_by_category.get(category_slug, []):
        keywords = split_keywords(row["starter_keywords"])
        exact_matches = [kw for kw in keywords if normalize(kw) in title_norm and normalize(kw)]
        score = len(exact_matches) * 10 + token_overlap_score(title_norm, keywords)
        if score > best["match_score"]:
            best = {
                "sub_category": row["sub_category"],
                "micro_niche": row["micro_niche"],
                "match_score": score,
                "matched_keywords": " | ".join(exact_matches),
                "my_fit": row["my_fit"],
                "selection_mode": row["selection_mode"],
                "selection_note": row["selection_note"],
            }
    if best["match_score"] == 0:
        best = {
            "sub_category": "Unmapped",
            "micro_niche": "Unmapped",
            "match_score": 0,
            "matched_keywords": "",
            "my_fit": "",
            "selection_mode": "",
            "selection_note": "No strong keyword match in taxonomy",
        }
    return best


def summarize_micro_niches(drilled_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in drilled_rows:
        key = (row["category_slug"], row["sub_category"], row["micro_niche"])
        grouped[key].append(row)

    summary = []
    for (category_slug, sub_category, micro_niche), rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: float(r.get("product_score", 0)), reverse=True)
        top = rows_sorted[0]
        summary.append(
            {
                "category_slug": category_slug,
                "category_name": top["category_name"],
                "sub_category": sub_category,
                "micro_niche": micro_niche,
                "candidate_count": len(rows),
                "avg_product_score": round(avg([to_float(r["product_score"]) for r in rows]), 2),
                "avg_category_score": round(avg([to_float(r["category_score"]) for r in rows]), 2),
                "avg_price": round(avg([to_float(r["price"]) for r in rows]), 2),
                "avg_sold_count": round(avg([to_float(r["sold_count"]) for r in rows]), 2),
                "top_product": top["product_title"],
                "top_product_score": to_float(top["product_score"]),
                "top_product_price": to_float(top["price"]),
                "top_product_sold": to_float(top["sold_count"]),
                "top_product_week_order": to_float(top["week_order"]),
                "top_product_signal": top["signal"],
                "matched_keywords": top.get("matched_keywords", ""),
            }
        )

    summary.sort(key=lambda x: (-x["avg_product_score"], -x["candidate_count"], x["category_slug"], x["sub_category"], x["micro_niche"]))
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict]) -> None:
    lines = [
        "# Product Drilldown",
        "",
        f"- rows: `{len(rows)}`",
        "",
        "## Top products by micro niche",
        "",
        "| category | sub category | micro niche | score | product | price | sold | week order | signal |",
        "|---|---|---|---:|---|---:|---:|---:|---|",
    ]
    for row in rows[:120]:
        lines.append(
            "| {category_name} | {sub_category} | {micro_niche} | {product_score} | {product_title} | {price} | {sold_count} | {week_order} | {signal} |".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_niche_markdown(path: Path, niche_rows: list[dict], drilled_rows: list[dict]) -> None:
    lines = [
        "# Micro Niche Summary",
        "",
        f"- micro niches: `{len(niche_rows)}`",
        "",
        "## Best micro niches",
        "",
        "| category | sub category | micro niche | count | avg score | top product | signal |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in niche_rows[:120]:
        lines.append(
            "| {category_name} | {sub_category} | {micro_niche} | {candidate_count} | {avg_product_score} | {top_product} | {top_product_signal} |".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_keywords(raw: str) -> list[str]:
    return [part.strip() for part in str(raw or "").split("|") if part.strip()]


def normalize(text: str) -> str:
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def token_overlap_score(title_norm: str, keywords: list[str]) -> int:
    title_tokens = set(title_norm.split())
    score = 0
    for kw in keywords:
        kw_norm = normalize(kw)
        kw_tokens = set(kw_norm.split())
        if not kw_tokens:
            continue
        overlap = len(title_tokens & kw_tokens)
        if overlap:
            score += overlap
    return score


def avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_csv(path: Path | str) -> list[dict]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
