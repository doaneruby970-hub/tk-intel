import argparse
import asyncio

from .category_capture import (
    export_category_capture_reports,
    import_search_capture_csv,
    import_shop_capture_csv,
)
from .category_scoring import score_categories_from_capture
from .capture_pack import build_capture_pack
from .db import connect, init_db, seed_reference_data
from .findniche_import import import_findniche_my, import_findniche_my_all_categories
from .importers import import_generic_csv, seed_sample_data
from .product_selection import select_products_from_capture
from .product_drilldown import build_product_drilldown
from .reporting import export_latest_reports
from .scanplan import build_scan_system
from .scoring import run_scoring
from .scraper import scrape_urls_to_db
from .taxonomy import build_category_radar_report


def prepare_db(conn) -> None:
    init_db(conn)
    seed_reference_data(conn)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TikTok Shop MY product intelligence CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create SQLite schema and seed categories/keywords")

    import_parser = subparsers.add_parser("import-csv", help="Import generic product snapshot CSV")
    import_parser.add_argument("--path", required=True, help="CSV file path")
    import_parser.add_argument("--region", default="MY", help="Default region")

    import_search_parser = subparsers.add_parser("import-search-capture", help="Import category search capture CSV")
    import_search_parser.add_argument("--path", required=True, help="Search capture CSV path")
    import_search_parser.add_argument("--region", default="MY", help="Region code")

    import_shop_parser = subparsers.add_parser("import-shop-capture", help="Import category shop capture CSV")
    import_shop_parser.add_argument("--path", required=True, help="Shop capture CSV path")

    seed_parser = subparsers.add_parser("seed-sample", help="Insert fictional sample data")
    seed_parser.add_argument("--region", default="MY", help="Sample region label")

    scrape_parser = subparsers.add_parser("scrape-urls", help="Scrape public product URLs from CSV")
    scrape_parser.add_argument("--input", required=True, help="Input CSV path")
    scrape_parser.add_argument("--region", default="MY", help="Region code")
    scrape_parser.add_argument("--locale", default="en-MY", help="Browser locale")
    scrape_parser.add_argument("--headless", default="true", choices=("true", "false"))
    scrape_parser.add_argument("--delay-ms", default=4500, type=int, help="Wait time after navigation")

    score_parser = subparsers.add_parser("score", help="Score latest products")
    score_parser.add_argument("--region", default="MY", help="Region code")
    score_parser.add_argument("--notes", default="", help="Optional note for this run")

    report_parser = subparsers.add_parser("report", help="Write latest CSV and Markdown report")
    report_parser.add_argument("--run-id", default="", help="Specific score run ID")

    category_report_parser = subparsers.add_parser("report-category-capture", help="Write category capture summary and exports")
    category_report_parser.add_argument("--capture-date", default="", help="Specific capture date in YYYY-MM-DD format")
    category_score_parser = subparsers.add_parser("score-categories", help="Score categories from captured product/shop samples")
    category_score_parser.add_argument("--capture-date", default="", help="Specific capture date in YYYY-MM-DD format")
    product_select_parser = subparsers.add_parser("select-products", help="Select product candidates from captured samples")
    product_select_parser.add_argument("--capture-date", default="", help="Specific capture date in YYYY-MM-DD format")
    product_select_parser.add_argument("--min-category-score", type=float, default=65.0, help="Minimum category score to consider")
    product_select_parser.add_argument("--top-n-per-category", type=int, default=8, help="Top products per category to include")
    product_drilldown_parser = subparsers.add_parser("drilldown-products", help="Drill product candidates into subcategories/micro niches")
    product_drilldown_parser.add_argument("--product-candidates", default="", help="Optional product candidates CSV path")

    subparsers.add_parser("build-category-radar", help="Build MY category radar Markdown and flat CSV")
    subparsers.add_parser("build-scan-system", help="Build MY full scan keyword pool, tasks, coverage, and playbook")
    capture_pack_parser = subparsers.add_parser("build-capture-pack", help="Build keyword queue and slotted capture workbooks")
    capture_pack_parser.add_argument("--capture-date", default="", help="Capture date in YYYY-MM-DD format")
    capture_pack_parser.add_argument("--product-slots-per-keyword", type=int, default=5, help="Blank product rows to generate per keyword")
    capture_pack_parser.add_argument("--shop-slots-per-category", type=int, default=12, help="Blank shop rows to generate per category")
    findniche_parser = subparsers.add_parser("import-findniche-my", help="Import real MY product/shop samples from FindNiche public pages")
    findniche_parser.add_argument("--capture-date", default="", help="Capture date in YYYY-MM-DD format")
    findniche_parser.add_argument("--limit-products", type=int, default=100, help="Maximum product rows to import")
    findniche_parser.add_argument("--limit-shops", type=int, default=100, help="Maximum shop rows to import")
    findniche_all_parser = subparsers.add_parser("import-findniche-my-all", help="Import real MY samples from all FindNiche category pages")
    findniche_all_parser.add_argument("--capture-date", default="", help="Capture date in YYYY-MM-DD format")
    findniche_all_parser.add_argument("--limit-products-per-category", type=int, default=50, help="Maximum product rows per category page")
    findniche_all_parser.add_argument("--limit-shops-per-category", type=int, default=30, help="Maximum shop rows per category page")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    conn = connect()
    try:
        if args.command == "init-db":
            prepare_db(conn)
            print("database initialized and reference data seeded")
            return

        if args.command == "import-csv":
            prepare_db(conn)
            count = import_generic_csv(conn, args.path, default_region=args.region)
            print(f"imported {count} product snapshot rows")
            return

        if args.command == "import-search-capture":
            prepare_db(conn)
            count = import_search_capture_csv(conn, args.path, region=args.region)
            print(f"imported {count} category product sample rows")
            return

        if args.command == "import-shop-capture":
            prepare_db(conn)
            count = import_shop_capture_csv(conn, args.path)
            print(f"imported {count} category shop sample rows")
            return

        if args.command == "seed-sample":
            prepare_db(conn)
            count = seed_sample_data(conn)
            print(f"inserted {count} sample snapshot rows")
            return

        if args.command == "scrape-urls":
            prepare_db(conn)
            headless = args.headless.lower() == "true"
            count = asyncio.run(
                scrape_urls_to_db(
                    conn,
                    input_csv=args.input,
                    region=args.region,
                    locale=args.locale,
                    headless=headless,
                    delay_ms=args.delay_ms,
                )
            )
            print(f"scraped and inserted {count} products")
            return

        if args.command == "score":
            prepare_db(conn)
            run_id = run_scoring(conn, region=args.region, notes=args.notes)
            print(f"score run created: {run_id}")
            return

        if args.command == "report":
            prepare_db(conn)
            csv_path, md_path = export_latest_reports(conn, run_id=args.run_id or None)
            print(f"wrote report CSV: {csv_path}")
            print(f"wrote report Markdown: {md_path}")
            return

        if args.command == "report-category-capture":
            prepare_db(conn)
            outputs = export_category_capture_reports(conn, capture_date=args.capture_date or None)
            print(f"wrote category summary CSV: {outputs['summary_csv']}")
            print(f"wrote category summary Markdown: {outputs['summary_md']}")
            print(f"wrote category product export: {outputs['product_csv']}")
            print(f"wrote category shop export: {outputs['shop_csv']}")
            return

        if args.command == "score-categories":
            prepare_db(conn)
            outputs = score_categories_from_capture(conn, capture_date=args.capture_date or None)
            print(f"wrote category score CSV: {outputs['csv_path']}")
            print(f"wrote category score Markdown: {outputs['md_path']}")
            return

        if args.command == "select-products":
            prepare_db(conn)
            outputs = select_products_from_capture(
                conn,
                capture_date=args.capture_date or None,
                min_category_score=args.min_category_score,
                top_n_per_category=args.top_n_per_category,
            )
            print(f"wrote product candidate CSV: {outputs['csv_path']}")
            print(f"wrote product candidate Markdown: {outputs['md_path']}")
            return

        if args.command == "drilldown-products":
            prepare_db(conn)
            outputs = build_product_drilldown(
                product_candidates_csv=args.product_candidates or None,
            )
            print(f"wrote product drilldown CSV: {outputs['csv_path']}")
            print(f"wrote product drilldown Markdown: {outputs['md_path']}")
            print(f"wrote micro niche summary CSV: {outputs['niche_csv_path']}")
            print(f"wrote micro niche summary Markdown: {outputs['niche_md_path']}")
            return

        if args.command == "build-category-radar":
            prepare_db(conn)
            md_path, csv_path = build_category_radar_report()
            print(f"wrote category radar Markdown: {md_path}")
            print(f"wrote category radar flat CSV: {csv_path}")
            return

        if args.command == "build-scan-system":
            prepare_db(conn)
            outputs = build_scan_system()
            print(f"wrote keyword pool: {outputs['keyword_pool_path']}")
            print(f"wrote scan tasks: {outputs['scan_tasks_path']}")
            print(f"wrote coverage summary: {outputs['coverage_path']}")
            print(f"wrote full scan playbook: {outputs['playbook_path']}")
            return

        if args.command == "build-capture-pack":
            prepare_db(conn)
            outputs = build_capture_pack(
                capture_date=args.capture_date or None,
                product_slots_per_keyword=args.product_slots_per_keyword,
                shop_slots_per_category=args.shop_slots_per_category,
            )
            print(f"wrote keyword queue: {outputs['keyword_queue_path']}")
            print(f"wrote product slots: {outputs['product_slots_path']}")
            print(f"wrote shop slots: {outputs['shop_slots_path']}")
            print(f"wrote search links: {outputs['links_path']}")
            print(f"wrote guide: {outputs['guide_path']}")
            return

        if args.command == "import-findniche-my":
            prepare_db(conn)
            result = import_findniche_my(
                conn,
                capture_date=args.capture_date or None,
                limit_products=args.limit_products,
                limit_shops=args.limit_shops,
            )
            print(f"imported FindNiche MY products: {result['product_count']}")
            print(f"imported FindNiche MY shops: {result['shop_count']}")
            print(f"wrote category summary CSV: {result['reports']['summary_csv']}")
            print(f"wrote category summary Markdown: {result['reports']['summary_md']}")
            return

        if args.command == "import-findniche-my-all":
            prepare_db(conn)
            result = import_findniche_my_all_categories(
                conn,
                capture_date=args.capture_date or None,
                limit_products_per_category=args.limit_products_per_category,
                limit_shops_per_category=args.limit_shops_per_category,
            )
            print(f"imported FindNiche MY all-category products: {result['product_count']}")
            print(f"imported FindNiche MY all-category shops: {result['shop_count']}")
            print(f"product categories covered: {result['category_count_products']}")
            print(f"shop categories covered: {result['category_count_shops']}")
            print(f"wrote category summary CSV: {result['reports']['summary_csv']}")
            print(f"wrote category summary Markdown: {result['reports']['summary_md']}")
            return
    finally:
        conn.close()


if __name__ == "__main__":
    main()
