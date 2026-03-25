"""Download Excel from online URL and parse into a DataFrame."""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# Allow running as `python scripts/fetch_data.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lib.config import (
    EXCEL_AUTH_TOKEN,
    EXCEL_HEADER_ROW,
    EXCEL_SHEET_NAME,
    EXCEL_SOURCE_URL,
    TEMP_EXCEL_PATH,
)
from src.lib.logger import get_logger

logger = get_logger(__name__)

# ── Month column mapping ────────────────────────────────────────────────────
# Handles both datetime objects and string labels in the header row.
MONTH_LABELS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]

_MONTH_COL_MAP: dict[str | datetime, str] = {}
for i, label in enumerate(MONTH_LABELS):
    month_num = ((i + 4 - 1) % 12) + 1  # Apr=4, May=5, … Mar=3
    year = 2025 if month_num >= 4 else 2026
    dt_key = datetime(year, month_num, 1)
    _MONTH_COL_MAP[dt_key] = label
    _MONTH_COL_MAP[label] = label

# Also map Timestamp objects (pandas sometimes converts dates to Timestamp)
try:
    for dt_key, label in list(_MONTH_COL_MAP.items()):
        if isinstance(dt_key, datetime):
            _MONTH_COL_MAP[pd.Timestamp(dt_key)] = label
except Exception:
    pass

# DB column names
MONTH_DB_COLS = {label: f"vol_{label.lower()}" for label in MONTH_LABELS}

# ── Expected info columns (for reference / validation) ──────────────────────
EXPECTED_INFO_COLS = [
    "Sr No.",
    "Name of the Dealer",
    "Distributor Name",
    "Dealer Segmentation",
    "Account Owner As per SF",
    "TM",
    "State",
    "Zone",
    "District",
]


def _download_excel(url: str, dest: Path, max_retries: int = 3) -> Path:
    """Download the Excel file with retry + exponential backoff."""
    headers: dict[str, str] = {}
    if EXCEL_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {EXCEL_AUTH_TOKEN}"

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Downloading Excel (attempt %d/%d)…", attempt, max_retries)
            resp = requests.get(url, headers=headers, timeout=60, stream=True)
            resp.raise_for_status()

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Saved %s (%d bytes)", dest.name, dest.stat().st_size)
            return dest
        except requests.RequestException as exc:
            logger.warning("Download failed (attempt %d): %s", attempt, exc)
            if attempt < max_retries:
                delay = 2 ** attempt
                logger.info("Retrying in %ds…", delay)
                time.sleep(delay)
            else:
                raise


def _rename_month_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename month columns (datetime or string) to short labels."""
    rename_map: dict = {}
    for col in df.columns:
        if col in _MONTH_COL_MAP:
            rename_map[col] = _MONTH_COL_MAP[col]
    if rename_map:
        df = df.rename(columns=rename_map)
        logger.debug("Renamed month columns: %s", list(rename_map.values()))
    return df


def fetch_excel(url: str | None = None) -> pd.DataFrame:
    """Download Excel from *url* and return a raw DataFrame.

    Parameters
    ----------
    url : str, optional
        Override the configured ``EXCEL_SOURCE_URL``.

    Returns
    -------
    pd.DataFrame
        Raw (uncleaned) data from the target sheet.
    """
    url = url or EXCEL_SOURCE_URL
    if not url:
        raise ValueError("EXCEL_SOURCE_URL is not set")

    path = _download_excel(url, TEMP_EXCEL_PATH)

    logger.info("Reading sheet '%s' (header row %d)…", EXCEL_SHEET_NAME, EXCEL_HEADER_ROW)
    df = pd.read_excel(
        path,
        sheet_name=EXCEL_SHEET_NAME,
        header=EXCEL_HEADER_ROW,
    )
    logger.info("Read %d rows × %d columns", len(df), len(df.columns))

    df = _rename_month_columns(df)
    return df


if __name__ == "__main__":
    df = fetch_excel()
    print(df.head())
    print(f"\nColumns: {list(df.columns)}")
