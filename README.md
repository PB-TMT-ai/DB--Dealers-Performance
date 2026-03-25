# Dealer Annual Tour Scheme — Automated Data Pipeline

Fetches dealer scheme data from an online Excel sheet, processes it, and syncs to a Supabase database.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your actual values

# 3. Set up database (run DDL in Supabase SQL editor or via RPC)
python scripts/setup_db.py

# 4. Run a one-time sync
python scripts/sync_data.py

# 5. Or start the scheduler (syncs every N hours)
python scripts/schedule_sync.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `EXCEL_SOURCE_URL` | Yes | Direct URL to the .xlsx file |
| `EXCEL_AUTH_TOKEN` | No | Bearer token for authenticated URLs |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key |
| `SUPABASE_ANON_KEY` | No | Supabase anon key |
| `SYNC_INTERVAL_HOURS` | No | Sync interval (default: 6) |
| `APP_ENV` | No | Environment name (default: development) |

## Project Structure

```
scripts/
  fetch_data.py      - Download Excel from URL
  setup_db.py        - Create Supabase tables
  sync_data.py       - Main sync orchestrator
  schedule_sync.py   - Optional scheduler
src/lib/
  config.py          - Env vars and constants
  logger.py          - Logging utility
  slab_config.py     - Slab thresholds and mappings
tests/
  test_sync.py       - Unit and integration tests
.workspace/          - Temp files (gitignored)
```

## Slab Qualification

| Slab | FY26 Total Volume (MT) |
|------|------------------------|
| A | 200–300 |
| B | 300–500 |
| C | 500–750 |
| D | 750–1250 |
| E | ≥1250 |
| No Slab | <200 |

## Cron Setup (Alternative to Scheduler)

```bash
# Sync every 6 hours
0 */6 * * * cd /path/to/project && python scripts/sync_data.py >> .workspace/cron.log 2>&1
```

## Excel URL Formats

- **SharePoint/OneDrive:** Direct download link (ends with `?download=1`)
- **Google Sheets:** `https://docs.google.com/spreadsheets/d/{ID}/export?format=xlsx`
- **Any hosted .xlsx:** Direct URL to the file

## Running Tests

```bash
pytest tests/ -v
```
