"""Optional scheduler: run sync on a recurring interval."""

from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schedule

from scripts.sync_data import run_sync
from src.lib.config import SYNC_INTERVAL_HOURS
from src.lib.logger import get_logger

logger = get_logger(__name__)

_running = True


def _shutdown(signum: int, _frame) -> None:
    global _running
    logger.info("Received signal %d, shutting down…", signum)
    _running = False


def _safe_sync() -> None:
    """Wrapper that catches exceptions so the scheduler keeps running."""
    try:
        exit_code = run_sync()
        if exit_code != 0:
            logger.warning("Sync returned non-zero exit code: %d", exit_code)
    except Exception:
        logger.exception("Unhandled error during scheduled sync")


def main() -> None:
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Scheduling sync every %d hour(s)", SYNC_INTERVAL_HOURS)
    schedule.every(SYNC_INTERVAL_HOURS).hours.do(_safe_sync)

    # Run immediately on start
    _safe_sync()

    while _running:
        schedule.run_pending()
        time.sleep(60)

    logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
