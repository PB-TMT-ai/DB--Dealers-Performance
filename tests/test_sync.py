"""Tests for slab logic, data processing, and sync flow."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.lib.slab_config import (
    count_lifting_frequency,
    determine_next_slab,
    determine_slab,
    volume_to_next_slab,
)


# ── Slab determination ──────────────────────────────────────────────────────

class TestDetermineSlab:
    def test_no_slab_below_200(self):
        assert determine_slab(0) == "No Slab"
        assert determine_slab(100) == "No Slab"
        assert determine_slab(199.99) == "No Slab"

    def test_slab_a(self):
        assert determine_slab(200) == "A"
        assert determine_slab(250) == "A"
        assert determine_slab(299.99) == "A"

    def test_slab_b(self):
        assert determine_slab(300) == "B"
        assert determine_slab(400) == "B"

    def test_slab_c(self):
        assert determine_slab(500) == "C"
        assert determine_slab(600) == "C"

    def test_slab_d(self):
        assert determine_slab(750) == "D"
        assert determine_slab(1000) == "D"

    def test_slab_e(self):
        assert determine_slab(1250) == "E"
        assert determine_slab(5000) == "E"


class TestNextSlab:
    def test_progression(self):
        assert determine_next_slab("No Slab") == "A"
        assert determine_next_slab("A") == "B"
        assert determine_next_slab("B") == "C"
        assert determine_next_slab("C") == "D"
        assert determine_next_slab("D") == "E"
        assert determine_next_slab("E") == "E"

    def test_invalid_slab(self):
        assert determine_next_slab("X") == "A"


class TestVolumeToNextSlab:
    def test_no_slab_to_a(self):
        assert volume_to_next_slab(100, "No Slab") == 100.0

    def test_a_to_b(self):
        assert volume_to_next_slab(250, "A") == 50.0

    def test_at_threshold(self):
        assert volume_to_next_slab(300, "B") == 200.0

    def test_slab_e_returns_zero(self):
        assert volume_to_next_slab(2000, "E") == 0.0


class TestLiftingFrequency:
    def test_all_zero(self):
        assert count_lifting_frequency([0] * 12) == 0

    def test_all_nonzero(self):
        assert count_lifting_frequency([10] * 12) == 12

    def test_mixed(self):
        assert count_lifting_frequency([0, 100, 0, 200, 0, 0, 50, 0, 0, 0, 0, 30]) == 4


# ── Month column renaming ───────────────────────────────────────────────────

class TestMonthColumnRenaming:
    def test_rename_datetime_columns(self):
        from scripts.fetch_data import _rename_month_columns

        cols = [datetime(2025, m, 1) for m in range(4, 13)] + [
            datetime(2026, m, 1) for m in range(1, 4)
        ]
        df = pd.DataFrame({c: [0] for c in cols})
        result = _rename_month_columns(df)
        expected = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
        assert list(result.columns) == expected

    def test_rename_string_columns(self):
        from scripts.fetch_data import _rename_month_columns

        labels = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
        df = pd.DataFrame({c: [0] for c in labels})
        result = _rename_month_columns(df)
        assert list(result.columns) == labels


# ── Data processing ──────────────────────────────────────────────────────────

class TestProcessDataframe:
    @pytest.fixture()
    def raw_df(self) -> pd.DataFrame:
        """Minimal DataFrame that mirrors the Excel schema after month rename."""
        return pd.DataFrame(
            {
                "Sr No.": ["1"],
                "Name of the Dealer": ["Test Dealer"],
                "Distributor Name": ["  Dist Co  "],
                "Dealer Segmentation": ["Seg1"],
                "Account Owner As per SF": ["Owner1"],
                "TM": ["TM1"],
                "State": ["maharashtra"],
                "Zone": ["West"],
                "District": ["Pune"],
                "Apr": [100],
                "May": [0],
                "Jun": ["50"],
                "Jul": [0],
                "Aug": [0],
                "Sep": [0],
                "Oct": [0],
                "Nov": [0],
                "Dec": [0],
                "Jan": [0],
                "Feb": [0],
                "Mar": [50],
                "FY 26 total": [200],
                "FY 25 vol.": [180],
                "Avg. monthly vol.": [16.67],
                "Distributor self-counter": ["yes"],
            }
        )

    def test_state_title_case(self, raw_df: pd.DataFrame):
        from scripts.sync_data import process_dataframe

        result = process_dataframe(raw_df)
        assert result.iloc[0]["state"] == "Maharashtra"

    def test_distributor_stripped(self, raw_df: pd.DataFrame):
        from scripts.sync_data import process_dataframe

        result = process_dataframe(raw_df)
        assert result.iloc[0]["distributor_name"] == "Dist Co"

    def test_self_counter_normalized(self, raw_df: pd.DataFrame):
        from scripts.sync_data import process_dataframe

        result = process_dataframe(raw_df)
        assert result.iloc[0]["self_counter"] == "Yes"

    def test_numeric_coercion(self, raw_df: pd.DataFrame):
        from scripts.sync_data import process_dataframe

        result = process_dataframe(raw_df)
        assert result.iloc[0]["vol_jun"] == 50.0

    def test_slab_derived(self, raw_df: pd.DataFrame):
        from scripts.sync_data import process_dataframe

        result = process_dataframe(raw_df)
        assert result.iloc[0]["qualified_slab"] == "A"

    def test_lifting_frequency(self, raw_df: pd.DataFrame):
        from scripts.sync_data import process_dataframe

        result = process_dataframe(raw_df)
        assert result.iloc[0]["lifting_frequency"] == 3  # Apr, Jun, Mar

    def test_null_dealer_dropped(self):
        from scripts.sync_data import process_dataframe

        df = pd.DataFrame(
            {
                "Sr No.": ["1", "2"],
                "Name of the Dealer": ["Valid", float("nan")],
                "Distributor Name": ["D1", "D2"],
                "FY 26 total": [100, 100],
            }
        )
        result = process_dataframe(df)
        assert len(result) == 1
        assert result.iloc[0]["dealer_name"] == "Valid"


# ── Sync flow (mocked) ──────────────────────────────────────────────────────

class TestRunSync:
    @patch("scripts.sync_data.upsert_to_supabase")
    @patch("scripts.sync_data.fetch_excel")
    def test_success(self, mock_fetch: MagicMock, mock_upsert: MagicMock):
        from scripts.sync_data import run_sync

        mock_fetch.return_value = pd.DataFrame(
            {
                "Sr No.": ["1"],
                "Name of the Dealer": ["Dealer A"],
                "Distributor Name": ["Dist A"],
                "FY 26 total": [500],
                "Apr": [50],
                "May": [40],
                "Jun": [0],
                "Jul": [0],
                "Aug": [0],
                "Sep": [0],
                "Oct": [0],
                "Nov": [0],
                "Dec": [0],
                "Jan": [0],
                "Feb": [0],
                "Mar": [0],
            }
        )
        mock_upsert.return_value = {"total": 1, "errors": 0}

        assert run_sync() == 0
        mock_fetch.assert_called_once()
        mock_upsert.assert_called_once()

    @patch("scripts.sync_data.fetch_excel", side_effect=Exception("network error"))
    def test_fetch_failure(self, mock_fetch: MagicMock):
        from scripts.sync_data import run_sync

        assert run_sync() == 1
