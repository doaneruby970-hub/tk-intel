from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = DATA_DIR / "reports"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
EXPORTS_DIR = DATA_DIR / "exports"
CAPTURE_PACK_DIR = DATA_DIR / "capture_pack"
CONFIG_DIR = ROOT_DIR / "config"
DB_PATH = DATA_DIR / "tk_intel.sqlite3"

CATEGORIES_PATH = CONFIG_DIR / "categories_my.csv"
KEYWORDS_PATH = CONFIG_DIR / "keywords_my.csv"
