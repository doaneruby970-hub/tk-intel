import csv
from collections import defaultdict
from pathlib import Path

from .settings import CONFIG_DIR, REPORTS_DIR


CATEGORY_RADAR_PATH = CONFIG_DIR / "category_radar_my.csv"
CATEGORY_TAXONOMY_PATH = CONFIG_DIR / "category_taxonomy_my.csv"
SCAN_MODES_PATH = CONFIG_DIR / "scan_modes_my.csv"
SCAN_RULES_PATH = CONFIG_DIR / "category_scan_rules_my.csv"


def build_scan_system(
    radar_csv: Path | str = CATEGORY_RADAR_PATH,
    taxonomy_csv: Path | str = CATEGORY_TAXONOMY_PATH,
    scan_modes_csv: Path | str = SCAN_MODES_PATH,
    scan_rules_csv: Path | str = SCAN_RULES_PATH,
    output_dir: Path | str = REPORTS_DIR,
) -> dict[str, Path]:
    radar_rows = _read_csv(radar_csv)
    taxonomy_rows = _read_csv(taxonomy_csv)
    mode_rows = _read_csv(scan_modes_csv)
    rule_rows = _read_csv(scan_rules_csv)

    radar_by_slug = {row["broad_category_slug"]: row for row in radar_rows}
    mode_by_name = {row["selection_mode"]: row for row in mode_rows}
    rules_by_slug = {row["broad_category_slug"]: row for row in rule_rows}

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    keyword_pool_rows = build_keyword_pool_rows(radar_rows, taxonomy_rows, mode_by_name)
    scan_task_rows = build_scan_task_rows(taxonomy_rows, radar_by_slug, rules_by_slug, mode_by_name)
    coverage_rows = build_coverage_rows(radar_rows, taxonomy_rows, keyword_pool_rows)

    keyword_pool_path = output_root / "my_keyword_pool_flat.csv"
    scan_tasks_path = output_root / "my_scan_tasks.csv"
    coverage_path = output_root / "my_category_coverage_summary.csv"
    playbook_path = output_root / "my_full_scan_playbook.md"

    _write_csv(keyword_pool_path, keyword_pool_rows)
    _write_csv(scan_tasks_path, scan_task_rows)
    _write_csv(coverage_path, coverage_rows)
    _write_playbook(playbook_path, radar_rows, coverage_rows, scan_task_rows, rules_by_slug)

    return {
        "keyword_pool_path": keyword_pool_path,
        "scan_tasks_path": scan_tasks_path,
        "coverage_path": coverage_path,
        "playbook_path": playbook_path,
    }


def build_keyword_pool_rows(radar_rows: list[dict], taxonomy_rows: list[dict], mode_by_name: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    for row in radar_rows:
        for keyword in split_keywords(row["starter_keywords"]):
            key = (row["broad_category_slug"], "", "", keyword)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "broad_category_slug": row["broad_category_slug"],
                    "broad_category_name": row["broad_category_name"],
                    "sub_category": "",
                    "micro_niche": "",
                    "keyword": keyword,
                    "source_level": "broad_category",
                    "research_priority": row["research_priority"],
                    "my_fit": "",
                    "selection_mode": "",
                    "entrypoints": "",
                    "primary_goal": "broad category discovery",
                }
            )

    for row in taxonomy_rows:
        mode = mode_by_name.get(row["selection_mode"], {})
        for keyword in split_keywords(row["starter_keywords"]):
            key = (row["broad_category_slug"], row["sub_category"], row["micro_niche"], keyword)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "broad_category_slug": row["broad_category_slug"],
                    "broad_category_name": "",
                    "sub_category": row["sub_category"],
                    "micro_niche": row["micro_niche"],
                    "keyword": keyword,
                    "source_level": "micro_niche",
                    "research_priority": "",
                    "my_fit": row["my_fit"],
                    "selection_mode": row["selection_mode"],
                    "entrypoints": mode.get("entrypoints", ""),
                    "primary_goal": mode.get("primary_goal", ""),
                }
            )

    rows.sort(key=lambda item: (item["broad_category_slug"], item["sub_category"], item["micro_niche"], item["keyword"]))
    return rows


def build_scan_task_rows(
    taxonomy_rows: list[dict],
    radar_by_slug: dict[str, dict],
    rules_by_slug: dict[str, dict],
    mode_by_name: dict[str, dict],
) -> list[dict]:
    rows: list[dict] = []
    for index, row in enumerate(taxonomy_rows, start=1):
        radar = radar_by_slug[row["broad_category_slug"]]
        rules = rules_by_slug[row["broad_category_slug"]]
        mode = mode_by_name.get(row["selection_mode"], {})
        keyword_count = len(split_keywords(row["starter_keywords"]))
        rows.append(
            {
                "task_id": f"TASK-{index:03d}",
                "scan_priority": rules["scan_priority"],
                "broad_category_slug": row["broad_category_slug"],
                "broad_category_name": radar["broad_category_name"],
                "sub_category": row["sub_category"],
                "micro_niche": row["micro_niche"],
                "my_fit": row["my_fit"],
                "selection_mode": row["selection_mode"],
                "entrypoints": mode.get("entrypoints", ""),
                "primary_goal": mode.get("primary_goal", ""),
                "keyword_count": keyword_count,
                "product_target_per_keyword": rules["product_target_per_keyword"],
                "shop_target_per_keyword": rules["shop_target_per_keyword"],
                "video_target_per_keyword": rules["video_target_per_keyword"],
                "live_target_per_keyword": rules["live_target_per_keyword"],
                "refresh_days": rules["refresh_days"],
                "starter_keywords": row["starter_keywords"],
                "selection_note": row["selection_note"],
                "scan_note": rules["scan_note"],
            }
        )
    return rows


def build_coverage_rows(radar_rows: list[dict], taxonomy_rows: list[dict], keyword_pool_rows: list[dict]) -> list[dict]:
    taxonomy_count: dict[str, int] = defaultdict(int)
    keyword_count: dict[str, int] = defaultdict(int)
    high_fit_count: dict[str, int] = defaultdict(int)

    for row in taxonomy_rows:
        slug = row["broad_category_slug"]
        taxonomy_count[slug] += 1
        if row["my_fit"] == "high":
            high_fit_count[slug] += 1

    for row in keyword_pool_rows:
        keyword_count[row["broad_category_slug"]] += 1

    rows = []
    for row in radar_rows:
        slug = row["broad_category_slug"]
        rows.append(
            {
                "broad_category_slug": slug,
                "broad_category_name": row["broad_category_name"],
                "research_priority": row["research_priority"],
                "subcategory_count": taxonomy_count[slug],
                "high_fit_micro_niches": high_fit_count[slug],
                "keyword_count": keyword_count[slug],
                "starter_keywords": row["starter_keywords"],
            }
        )
    return rows


def _write_playbook(
    path: Path,
    radar_rows: list[dict],
    coverage_rows: list[dict],
    scan_task_rows: list[dict],
    rules_by_slug: dict[str, dict],
) -> None:
    coverage_by_slug = {row["broad_category_slug"]: row for row in coverage_rows}
    tasks_by_priority: dict[str, list[dict]] = defaultdict(list)
    for task in scan_task_rows:
        tasks_by_priority[task["scan_priority"]].append(task)

    lines = [
        "# Malaysia Full Scan Playbook",
        "",
        "This playbook turns the category radar into an execution system.",
        "",
        "## What is included",
        "",
        "- `my_keyword_pool_flat.csv`: flattened keyword pool for all categories",
        "- `my_scan_tasks.csv`: micro-niche level scan tasks",
        "- `my_category_coverage_summary.csv`: coverage counts by broad category",
        "",
        "## Broad-scan workflow",
        "",
        "1. Start from broad category priority, not from random products.",
        "2. For each category, use the flattened keyword pool to scan search, videos, live, or reviews depending on mode.",
        "3. Capture only the top sample first: product ranking, shop concentration, price band, and proof signals.",
        "4. Promote only the strongest categories into repeated snapshot tracking.",
        "",
        "## Coverage summary",
        "",
        "| category | priority | subcategory count | high-fit micro niches | keyword count |",
        "|---|---|---:|---:|---:|",
    ]
    for row in coverage_rows:
        lines.append(
            "| {broad_category_name} | {research_priority} | {subcategory_count} | {high_fit_micro_niches} | {keyword_count} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Scan quotas by broad category",
            "",
            "| category | scan priority | broad keywords | products per keyword | shops per keyword | videos per keyword | live per keyword | refresh days |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in radar_rows:
        rules = rules_by_slug[row["broad_category_slug"]]
        lines.append(
            "| {name} | {priority} | {broad_keywords} | {product_target} | {shop_target} | {video_target} | {live_target} | {refresh_days} |".format(
                name=row["broad_category_name"],
                priority=rules["scan_priority"],
                broad_keywords=rules["broad_scan_keywords"],
                product_target=rules["product_target_per_keyword"],
                shop_target=rules["shop_target_per_keyword"],
                video_target=rules["video_target_per_keyword"],
                live_target=rules["live_target_per_keyword"],
                refresh_days=rules["refresh_days"],
            )
        )

    for priority in ("core", "watch", "cautious", "late"):
        tasks = tasks_by_priority.get(priority, [])
        if not tasks:
            continue
        lines.extend([f"", f"## {priority.title()} task examples", "", "| category | subcategory | micro niche | mode | starter keywords | note |", "|---|---|---|---|---|---|"])
        for task in tasks[:20]:
            lines.append(
                "| {broad_category_name} | {sub_category} | {micro_niche} | {selection_mode} | {starter_keywords} | {selection_note} |".format(
                    **task
                )
            )

    lines.extend(
        [
            "",
            "## Daily capture rule",
            "",
            "- For each scanned keyword, record the first 20-40 visible product candidates depending on category priority.",
            "- For each keyword, capture at least the top 5-12 shops depending on the category rule.",
            "- If a mode includes `live`, sample at least one live room and note whether the same products repeat.",
            "- If a mode includes `review`, record repeated complaint themes before deciding the category is viable.",
            "",
            "## Promotion rule",
            "",
            "- Promote a micro niche if search stability, creator proof, and price band all look usable.",
            "- Demote a micro niche if it is saturated, over-dependent on one seller, or has obvious compliance risk.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def split_keywords(raw: str) -> list[str]:
    return [part.strip() for part in str(raw or "").split("|") if part.strip()]


def _read_csv(path: Path | str) -> list[dict]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
