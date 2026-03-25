"""Create (or validate) the dealers table in Supabase."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.lib.config import get_supabase_client
from src.lib.logger import get_logger

logger = get_logger(__name__)

DEALERS_TABLE_DDL = """\
CREATE TABLE IF NOT EXISTS dealers (
    id SERIAL PRIMARY KEY,
    sr_no TEXT,
    dealer_name TEXT NOT NULL,
    distributor_name TEXT,
    dealer_segmentation TEXT,
    account_owner TEXT,
    tm TEXT,
    state TEXT DEFAULT 'Unknown',
    zone TEXT DEFAULT 'Unknown',
    district TEXT DEFAULT '',
    vol_apr NUMERIC DEFAULT 0,
    vol_may NUMERIC DEFAULT 0,
    vol_jun NUMERIC DEFAULT 0,
    vol_jul NUMERIC DEFAULT 0,
    vol_aug NUMERIC DEFAULT 0,
    vol_sep NUMERIC DEFAULT 0,
    vol_oct NUMERIC DEFAULT 0,
    vol_nov NUMERIC DEFAULT 0,
    vol_dec NUMERIC DEFAULT 0,
    vol_jan NUMERIC DEFAULT 0,
    vol_feb NUMERIC DEFAULT 0,
    vol_mar NUMERIC DEFAULT 0,
    fy26_total NUMERIC DEFAULT 0,
    fy25_volume NUMERIC DEFAULT 0,
    avg_monthly_vol NUMERIC DEFAULT 0,
    self_counter TEXT DEFAULT 'No',
    qualified_slab TEXT DEFAULT 'No Slab',
    lifting_frequency INTEGER DEFAULT 0,
    next_upgrade_slab TEXT,
    vol_to_next_slab NUMERIC DEFAULT 0,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (dealer_name, distributor_name)
);
"""


def create_dealers_table() -> None:
    """Execute DDL to create the dealers table via Supabase RPC.

    Requires a Postgres function ``exec_sql(query text)`` to be registered
    in Supabase, **or** you can run the DDL directly in the Supabase SQL
    editor.  The function is attempted first; if it doesn't exist the DDL
    is printed for manual execution.
    """
    client = get_supabase_client()

    try:
        client.rpc("exec_sql", {"query": DEALERS_TABLE_DDL}).execute()
        logger.info("dealers table created / verified via RPC")
    except Exception as exc:
        logger.warning(
            "RPC exec_sql not available (%s). "
            "Please run the following DDL in the Supabase SQL editor:",
            exc,
        )
        print("\n" + DEALERS_TABLE_DDL)
        print(
            "Tip: Create a Postgres function to allow DDL from the client:\n"
            "  CREATE OR REPLACE FUNCTION exec_sql(query text)\n"
            "  RETURNS void LANGUAGE plpgsql AS $$\n"
            "  BEGIN EXECUTE query; END; $$;\n"
        )


if __name__ == "__main__":
    create_dealers_table()
