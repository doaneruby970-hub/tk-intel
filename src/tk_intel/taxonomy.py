import csv
from collections import defaultdict
from pathlib import Path

from .settings import CONFIG_DIR, REPORTS_DIR


CATEGORY_RADAR_PATH = CONFIG_DIR / "category_radar_my.csv"
CATEGORY_TAXONOMY_PATH = CONFIG_DIR / "category_taxonomy_my.csv"


def build_category_radar_report(
    radar_csv: Path | str = CATEGORY_RADAR_PATH,
    taxonomy_csv: Path | str = CATEGORY_TAXONOMY_PATH,
    output_dir: Path | str = REPORTS_DIR,
) -> tuple[Path, Path]:
    radar_rows = _read_csv(radar_csv)
    taxonomy_rows = _read_csv(taxonomy_csv)

    taxonomy_by_slug: dict[str, list[dict]] = defaultdict(list)
    for row in taxonomy_rows:
        taxonomy_by_slug[row["broad_category_slug"]].append(row)

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    md_path = output_root / "my_category_radar.md"
    csv_path = output_root / "my_category_radar_flat.csv"

    write_flat_csv(csv_path, taxonomy_rows)
    write_markdown(md_path, radar_rows, taxonomy_by_slug)
    return md_path, csv_path


def write_flat_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, radar_rows: list[dict], taxonomy_by_slug: dict[str, list[dict]]) -> None:
    lines = [
        "# Malaysia Category Radar",
        "",
        "This is a research taxonomy for TikTok Shop Malaysia.",
        "",
        "It is not claimed as a full official leaf-category export from TikTok.",
        "It combines:",
        "",
        "1. TikTok Shop official creator-facing top-level categories",
        "2. FindNiche's Malaysia broad category list",
        "3. EchoTik's Malaysia Q1 2025 category signals",
        "4. Practical e-commerce subcategory splits for selection work",
        "",
        "## Broad category radar",
        "",
        "| broad category | bucket | signal | priority | content fit | logistics risk | compliance risk | starter keywords |",
        "|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in radar_rows:
        lines.append(
            "| {broad_category_name} | {official_creator_bucket} | {source_signal} | {research_priority} | {content_fit} | {logistics_risk} | {compliance_risk} | {starter_keywords} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Priority guide",
            "",
            "- `core`: broad-scan and deep-track early",
            "- `watch`: broad-scan now and deepen if product signals are good",
            "- `cautious`: keep visible but validate ops/compliance before scaling",
            "- `late`: map the category now but postpone until the workflow is stable",
        ]
    )

    grouped_by_priority: dict[str, list[dict]] = defaultdict(list)
    for row in radar_rows:
        grouped_by_priority[row["research_priority"]].append(row)

    for priority in ("core", "watch", "cautious", "late"):
        category_rows = grouped_by_priority.get(priority, [])
        if not category_rows:
            continue
        lines.extend([f"", f"## {priority.title()} categories", ""])
        for row in category_rows:
            lines.append(f"### {row['broad_category_name']}")
            lines.append("")
            lines.append(f"- Bucket: `{row['official_creator_bucket']}`")
            lines.append(f"- Signal: `{row['source_signal']}`")
            lines.append(f"- Note: {row['market_note']}")
            lines.append(f"- Starter keywords: `{row['starter_keywords']}`")
            lines.append("")
            lines.append("| subcategory | micro niche | MY fit | mode | note | starter keywords |")
            lines.append("|---|---|---|---|---|---|")
            for item in taxonomy_by_slug.get(row["broad_category_slug"], []):
                lines.append(
                    "| {sub_category} | {micro_niche} | {my_fit} | {selection_mode} | {selection_note} | {starter_keywords} |".format(
                        **item
                    )
                )
            lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_csv(path: Path | str) -> list[dict]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))
