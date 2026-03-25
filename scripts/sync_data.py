"""Main sync orchestrator: fetch → process → upsert."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.fetch_data import MONTH_DB_COLS, MONTH_LABELS, fetch_excel
from src.lib.config import EXCEL_SOURCE_URL, get_supabase_client
from src.lib.logger import get_logger
from src.lib.slab_config import (
    count_lifting_frequency,
    determine_next_slab,
    determine_slab,
    volume_to_next_slab,
)

logger = get_logger(__name__)

# ── Column mappings (Excel header → DB column) ──────────────────────────────
INFO_COL_MAP = {
    "Sr No.": "sr_no",
    "Name of the Dealer": "dealer_name",
    "Distributor Name": "distributor_name",
    "Dealer Segmentation": "dealer_segmentation",
    "Account Owner As per SF": "account_owner",
    "TM": "tm",
    "State": "state",
    "Zone": "zone",
    "District": "district",
}

AGGREGATE_COL_MAP = {
    "FY 26 total": "fy26_total",
    "FY 25 vol.": "fy25_volume",
    "Avg. monthly vol.": "avg_monthly_vol",
}

FLAG_COL_MAP = {
    "Distributor self-counter": "self_counter",
}

UPSERT_BATCH_SIZE = 500


# ── Processing ───────────────────────────────────────────────────────────────

def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean, transform, and derive columns from the raw Excel data."""

    # 1. Rename info columns
    df = df.rename(columns=INFO_COL_MAP)

    # 2. Rename month columns to DB names (Apr → vol_apr, etc.)
    month_rename = {label: db_col for label, db_col in MONTH_DB_COLS.items() if label in df.columns}
    df = df.rename(columns=month_rename)

    # 3. Rename aggregate columns
    agg_rename = {k: v for k, v in AGGREGATE_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=agg_rename)

    # 4. Rename flag columns
    flag_rename = {k: v for k, v in FLAG_COL_MAP.items() if k in df.columns}
    df = df.rename(columns=flag_rename)

    # 5. Numeric conversion for volume + aggregate columns
    vol_cols = [f"vol_{m.lower()}" for m in MONTH_LABELS]
    agg_cols = ["fy26_total", "fy25_volume", "avg_monthly_vol"]
    for col in vol_cols + agg_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # 6. Clean string columns
    # State: title case, "Unknown" for NaN/invalid
    if "state" in df.columns:
        df["state"] = (
            df["state"]
            .astype(str)
            .str.strip()
            .str.title()
            .replace({"Nan": "Unknown", "None": "Unknown", "0": "Unknown", "": "Unknown"})
        )

    # Zone: keep as-is, "Unknown" for NaN
    if "zone" in df.columns:
        df["zone"] = (
            df["zone"]
            .astype(str)
            .str.strip()
            .replace({"nan": "Unknown", "None": "Unknown", "0": "Unknown", "": "Unknown"})
        )

    # District: strip whitespace, empty string for 0/NaN
    if "district" in df.columns:
        df["district"] = (
            df["district"]
            .astype(str)
            .str.strip()
            .replace({"nan": "", "None": "", "0": ""})
        )

    # Distributor name: strip whitespace
    if "distributor_name" in df.columns:
        df["distributor_name"] = df["distributor_name"].astype(str).str.strip()
        df["distributor_name"] = df["distributor_name"].replace({"nan": "", "None": ""})

    # Self-counter flag: normalize to Yes/No
    if "self_counter" in df.columns:
        df["self_counter"] = (
            df["self_counter"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(lambda v: "Yes" if v in ("yes", "y", "true", "1") else "No")
        )
    else:
        df["self_counter"] = "No"

    # 7. Drop rows where dealer_name is missing
    if "dealer_name" in df.columns:
        df = df[df["dealer_name"].notna()].copy()
        df["dealer_name"] = df["dealer_name"].astype(str).str.strip()
        df = df[~df["dealer_name"].str.lower().isin(["", "nan", "none"])].copy()
    else:
        logger.error("Column 'dealer_name' not found after renaming")
        return df

    # 8. Derive columns
    if "fy26_total" in df.columns:
        df["qualified_slab"] = df["fy26_total"].apply(determine_slab)
        df["next_upgrade_slab"] = df["qualified_slab"].apply(determine_next_slab)
        df["vol_to_next_slab"] = df.apply(
            lambda r: volume_to_next_slab(r["fy26_total"], r["qualified_slab"]),
            axis=1,
        )
    else:
        df["qualified_slab"] = "No Slab"
        df["next_upgrade_slab"] = "A"
        df["vol_to_next_slab"] = 200.0

    # Lifting frequency: count non-zero months
    existing_vol_cols = [c for c in vol_cols if c in df.columns]
    if existing_vol_cols:
        df["lifting_frequency"] = df[existing_vol_cols].apply(
            lambda row: count_lifting_frequency(row.tolist()), axis=1
        )
    else:
        df["lifting_frequency"] = 0

    # 9. Timestamp
    df["last_synced_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("Processed %d rows", len(df))
    return df


# ── Upsert ───────────────────────────────────────────────────────────────────

# DB columns we actually write (order doesn't matter for upsert)
DB_COLUMNS = [
    "sr_no", "dealer_name", "distributor_name", "dealer_segmentation",
    "account_owner", "tm", "state", "zone", "district",
    *[f"vol_{m.lower()}" for m in MONTH_LABELS],
    "fy26_total", "fy25_volume", "avg_monthly_vol",
    "self_counter", "qualified_slab", "lifting_frequency",
    "next_upgrade_slab", "vol_to_next_slab", "last_synced_at",
]


def _to_records(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts containing only DB_COLUMNS."""
    available = [c for c in DB_COLUMNS if c in df.columns]
    records = df[available].to_dict(orient="records")
    # Convert NaN / numpy types to Python-native for JSON serialization
    clean: list[dict] = []
    for rec in records:
        row = {}
        for k, v in rec.items():
            if pd.isna(v):
                row[k] = None
            elif hasattr(v, "item"):  # numpy scalar
                row[k] = v.item()
            else:
                row[k] = v
        clean.append(row)
    return clean


def upsert_to_supabase(df: pd.DataFrame) -> dict[str, int]:
    """Batch-upsert records into the dealers table.

    Returns
    -------
    dict with keys: total, errors
    """
    client = get_supabase_client()
    records = _to_records(df)
    total = len(records)
    errors = 0

    for start in range(0, total, UPSERT_BATCH_SIZE):
        batch = records[start : start + UPSERT_BATCH_SIZE]
        batch_num = start // UPSERT_BATCH_SIZE + 1

        for attempt in range(1, 4):
            try:
                client.table("dealers").upsert(
                    batch, on_conflict="dealer_name,distributor_name"
                ).execute()
                logger.debug("Batch %d (%d rows) upserted", batch_num, len(batch))
                break
            except Exception as exc:
                logger.warning(
                    "Batch %d failed (attempt %d): %s", batch_num, attempt, exc
                )
                if attempt < 3:
                    time.sleep(2 ** attempt)
                else:
                    logger.error("Batch %d failed permanently", batch_num)
                    errors += len(batch)

    logger.info("Upsert complete: %d total, %d errors", total, errors)
    return {"total": total, "errors": errors}


# ── Orchestrator ─────────────────────────────────────────────────────────────

def run_sync() -> int:
    """Run the full sync pipeline. Returns 0 on success, 1 on failure."""
    start_time = time.monotonic()
    try:
        logger.info("=== Sync started ===")

        # Fetch
        df = fetch_excel(EXCEL_SOURCE_URL)
        logger.info("Fetched %d rows from Excel", len(df))

        # Process
        df = process_dataframe(df)

        # Upsert
        result = upsert_to_supabase(df)

        elapsed = time.monotonic() - start_time
        logger.info(
            "=== Sync completed in %.1fs — %d rows, %d errors ===",
            elapsed,
            result["total"],
            result["errors"],
        )
        return 0 if result["errors"] == 0 else 1

    except Exception:
        elapsed = time.monotonic() - start_time
        logger.exception("=== Sync FAILED after %.1fs ===", elapsed)
        return 1


if __name__ == "__main__":
    sys.exit(run_sync())
