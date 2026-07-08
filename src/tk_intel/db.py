import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from .settings import CATEGORIES_PATH, DB_PATH, KEYWORDS_PATH


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            category_slug TEXT PRIMARY KEY,
            category_name TEXT NOT NULL,
            priority_tier TEXT NOT NULL,
            content_fit INTEGER DEFAULT 3,
            logistics_risk INTEGER DEFAULT 3,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_slug TEXT NOT NULL,
            keyword TEXT NOT NULL,
            priority INTEGER DEFAULT 2,
            locale TEXT DEFAULT 'en-MY',
            UNIQUE(category_slug, keyword, locale),
            FOREIGN KEY (category_slug) REFERENCES categories(category_slug)
        );

        CREATE TABLE IF NOT EXISTS products (
            product_key TEXT PRIMARY KEY,
            product_id TEXT,
            region TEXT NOT NULL,
            title TEXT NOT NULL,
            category_slug TEXT NOT NULL,
            shop_name TEXT DEFAULT '',
            shop_url TEXT DEFAULT '',
            product_url TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_slug) REFERENCES categories(category_slug)
        );

        CREATE TABLE IF NOT EXISTS product_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_key TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            keyword TEXT DEFAULT '',
            source_type TEXT DEFAULT 'manual_csv',
            currency TEXT DEFAULT 'MYR',
            price REAL DEFAULT 0,
            original_price REAL,
            sold_count INTEGER DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            creator_count INTEGER DEFAULT 0,
            video_count INTEGER DEFAULT 0,
            competitor_count INTEGER DEFAULT 0,
            stock_status TEXT DEFAULT '',
            raw_path TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            UNIQUE(product_key, captured_at, keyword, source_type),
            FOREIGN KEY (product_key) REFERENCES products(product_key)
        );

        CREATE TABLE IF NOT EXISTS score_runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            region TEXT NOT NULL,
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS product_scores (
            run_id TEXT NOT NULL,
            product_key TEXT NOT NULL,
            category_slug TEXT NOT NULL,
            title TEXT NOT NULL,
            keyword TEXT DEFAULT '',
            shop_name TEXT DEFAULT '',
            latest_captured_at TEXT NOT NULL,
            latest_price REAL DEFAULT 0,
            sold_count INTEGER DEFAULT 0,
            sold_delta INTEGER DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            review_delta INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            demand_score REAL DEFAULT 0,
            growth_score REAL DEFAULT 0,
            competition_score REAL DEFAULT 0,
            margin_proxy_score REAL DEFAULT 0,
            risk_score REAL DEFAULT 0,
            opportunity_score REAL DEFAULT 0,
            opportunity_band TEXT DEFAULT '',
            rationale TEXT DEFAULT '',
            PRIMARY KEY (run_id, product_key),
            FOREIGN KEY (run_id) REFERENCES score_runs(run_id),
            FOREIGN KEY (product_key) REFERENCES products(product_key)
        );

        CREATE TABLE IF NOT EXISTS category_product_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capture_date TEXT NOT NULL,
            broad_category_slug TEXT NOT NULL,
            sub_category TEXT DEFAULT '',
            micro_niche TEXT DEFAULT '',
            keyword TEXT DEFAULT '',
            rank INTEGER DEFAULT 0,
            shop_name TEXT DEFAULT '',
            product_title TEXT NOT NULL,
            price REAL DEFAULT 0,
            currency TEXT DEFAULT 'MYR',
            sold_count INTEGER DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            product_url TEXT DEFAULT '',
            shop_url TEXT DEFAULT '',
            video_flag INTEGER DEFAULT 0,
            live_flag INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(capture_date, broad_category_slug, keyword, product_url, shop_name)
        );

        CREATE TABLE IF NOT EXISTS category_shop_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capture_date TEXT NOT NULL,
            broad_category_slug TEXT NOT NULL,
            shop_name TEXT NOT NULL,
            shop_url TEXT DEFAULT '',
            category_focus TEXT DEFAULT '',
            shop_rating REAL DEFAULT 0,
            product_count INTEGER DEFAULT 0,
            hero_products TEXT DEFAULT '',
            price_band TEXT DEFAULT '',
            content_style TEXT DEFAULT '',
            live_intensity TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(capture_date, broad_category_slug, shop_url, shop_name)
        );
        """
    )
    conn.commit()


def make_product_key(product_id: str, product_url: str, region: str) -> str:
    if product_id:
        return f"{region}:{product_id}"
    return f"{region}:{product_url.strip()}"


def seed_reference_data(
    conn: sqlite3.Connection,
    categories_path: Path | str = CATEGORIES_PATH,
    keywords_path: Path | str = KEYWORDS_PATH,
) -> None:
    with open(categories_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    for row in rows:
        conn.execute(
            """
            INSERT INTO categories (
                category_slug, category_name, priority_tier, content_fit, logistics_risk, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(category_slug) DO UPDATE SET
                category_name = excluded.category_name,
                priority_tier = excluded.priority_tier,
                content_fit = excluded.content_fit,
                logistics_risk = excluded.logistics_risk,
                notes = excluded.notes
            """,
            (
                row["category_slug"].strip(),
                row["category_name"].strip(),
                row["priority_tier"].strip(),
                int(row.get("content_fit", 3) or 3),
                int(row.get("logistics_risk", 3) or 3),
                row.get("notes", "").strip(),
            ),
        )

    conn.execute("DELETE FROM keywords")
    with open(keywords_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        keyword_rows = list(reader)
    conn.executemany(
        """
        INSERT INTO keywords (category_slug, keyword, priority, locale)
        VALUES (?, ?, ?, ?)
        """,
        [
            (
                row["category_slug"].strip(),
                row["keyword"].strip(),
                int(row.get("priority", 2) or 2),
                row.get("locale", "en-MY").strip(),
            )
            for row in keyword_rows
        ],
    )
    conn.commit()


def upsert_product_snapshot(conn: sqlite3.Connection, record: dict) -> str:
    product_id = str(record.get("product_id", "") or "").strip()
    product_url = str(record.get("product_url", "") or "").strip()
    region = str(record.get("region", "MY") or "MY").strip().upper()
    product_key = make_product_key(product_id, product_url, region)

    conn.execute(
        """
        INSERT INTO products (
            product_key, product_id, region, title, category_slug, shop_name, shop_url, product_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_key) DO UPDATE SET
            product_id = excluded.product_id,
            title = excluded.title,
            category_slug = excluded.category_slug,
            shop_name = excluded.shop_name,
            shop_url = excluded.shop_url,
            product_url = excluded.product_url
        """,
        (
            product_key,
            product_id,
            region,
            str(record.get("title", "") or "").strip(),
            str(record.get("category_slug", "") or "").strip(),
            str(record.get("shop_name", "") or "").strip(),
            str(record.get("shop_url", "") or "").strip(),
            product_url,
        ),
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO product_snapshots (
            product_key, captured_at, keyword, source_type, currency, price, original_price,
            sold_count, review_count, rating, creator_count, video_count, competitor_count,
            stock_status, raw_path, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_key,
            str(record.get("captured_at", "") or "").strip(),
            str(record.get("keyword", "") or "").strip(),
            str(record.get("source_type", "manual_csv") or "manual_csv").strip(),
            str(record.get("currency", "MYR") or "MYR").strip(),
            float(record.get("price", 0) or 0),
            _to_optional_float(record.get("original_price")),
            int(record.get("sold_count", 0) or 0),
            int(record.get("review_count", 0) or 0),
            float(record.get("rating", 0) or 0),
            int(record.get("creator_count", 0) or 0),
            int(record.get("video_count", 0) or 0),
            int(record.get("competitor_count", 0) or 0),
            str(record.get("stock_status", "") or "").strip(),
            str(record.get("raw_path", "") or "").strip(),
            str(record.get("notes", "") or "").strip(),
        ),
    )
    conn.commit()
    return product_key


def latest_score_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM score_runs ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return None if row is None else str(row["run_id"])


def fetch_rows(conn: sqlite3.Connection, query: str, params: Iterable | None = None) -> list[sqlite3.Row]:
    return list(conn.execute(query, tuple(params or ())).fetchall())


def _to_optional_float(value: object) -> float | None:
    if value in (None, "", "null"):
        return None
    return float(value)
