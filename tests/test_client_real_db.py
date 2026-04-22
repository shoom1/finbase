"""
Real-database regression tests for DataClient.

The mocked tests in `test_client.py` exercise control flow but cannot catch
SQL-shaped bugs (parameter binding, NULL semantics, etc.). These tests run
against a temp SQLite db and assert end-to-end behavior for the methods
that pass through to `TimeSeriesDB.query`.

Specifically: `get_all` and `get_data(start=None, end=None)` previously
silently returned empty results because `WHERE date >= NULL` evaluates to
NULL in SQL. This module exists to keep that bug fixed.
"""

import pandas as pd
import pytest

from finbase.client.client import DataClient


@pytest.fixture
def real_client(temp_db_path, multiple_symbols_db):
    """DataClient pointed at a temp db prepopulated with AAPL/MSFT/JPM."""
    return DataClient(db_path=temp_db_path)


class TestGetAllRealDB:
    """Regression: get_all() must return all available rows."""

    def test_get_all_single_symbol_returns_rows(self, real_client):
        df = real_client.get_all("AAPL", columns=["close"])
        assert not df.empty, "get_all returned empty for a populated symbol"
        assert (df["symbol"] == "AAPL").all()
        assert (df["metric"] == "close").all()
        assert df["value"].notna().all()

    def test_get_all_multiple_symbols(self, real_client):
        df = real_client.get_all(["AAPL", "MSFT"], columns=["close"])
        assert not df.empty
        assert set(df["symbol"].unique()) == {"AAPL", "MSFT"}

    def test_get_all_default_columns(self, real_client):
        df = real_client.get_all("AAPL")
        assert not df.empty
        # Should pull every OHLCV column that has data
        assert set(df["metric"].unique()) >= {"close", "open", "high", "low", "volume"}


class TestGetDataNoneDates:
    """Regression: get_data with start=None/end=None must not silently empty."""

    def test_get_data_no_dates_returns_rows(self, real_client):
        df = real_client.get_data("AAPL", columns=["close"])
        assert not df.empty

    def test_get_data_only_start_returns_rows(self, real_client):
        df = real_client.get_data("AAPL", start="2024-01-01", columns=["close"])
        assert not df.empty

    def test_get_data_only_end_returns_rows(self, real_client):
        df = real_client.get_data("AAPL", end="2024-12-31", columns=["close"])
        assert not df.empty

    def test_get_data_both_dates_returns_rows(self, real_client):
        df = real_client.get_data(
            "AAPL", start="2024-01-01", end="2024-01-31", columns=["close"]
        )
        assert not df.empty


class TestTimeSeriesDBQueryNoneDates:
    """Test the underlying TimeSeriesDB.query directly."""

    def test_query_with_none_start_and_end(self, multiple_symbols_db):
        df = multiple_symbols_db.query(
            symbols=["AAPL"],
            start_date=None,
            end_date=None,
            column="close",
        )
        assert not df.empty, "query with None dates returned empty"

    def test_query_with_none_start_only(self, multiple_symbols_db):
        df = multiple_symbols_db.query(
            symbols=["AAPL"],
            start_date=None,
            end_date="2024-12-31",
            column="close",
        )
        assert not df.empty

    def test_query_with_none_end_only(self, multiple_symbols_db):
        df = multiple_symbols_db.query(
            symbols=["AAPL"],
            start_date="2024-01-01",
            end_date=None,
            column="close",
        )
        assert not df.empty
