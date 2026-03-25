"""Configuration: environment variables and constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKSPACE_DIR = PROJECT_ROOT / ".workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)
LOG_FILE_PATH = WORKSPACE_DIR / "sync.log"
TEMP_EXCEL_PATH = WORKSPACE_DIR / "latest_data.xlsx"

# ── Excel source ─────────────────────────────────────────────────────────────
EXCEL_SOURCE_URL: str = os.environ.get("EXCEL_SOURCE_URL", "")
EXCEL_AUTH_TOKEN: str = os.environ.get("EXCEL_AUTH_TOKEN", "")
EXCEL_SHEET_NAME: str = "FY 26_qualification scenario"
EXCEL_HEADER_ROW: int = 2  # 0-indexed

# ── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY: str = os.environ.get("SUPABASE_SERVICE_KEY", "")

# ── Sync ─────────────────────────────────────────────────────────────────────
SYNC_INTERVAL_HOURS: int = int(os.environ.get("SYNC_INTERVAL_HOURS", "6"))
APP_ENV: str = os.environ.get("APP_ENV", "development")

# ── Supabase client (lazy singleton) ─────────────────────────────────────────
_supabase_client = None


def get_supabase_client():
    """Return a cached Supabase client instance."""
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        from supabase import create_client

        _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_client
