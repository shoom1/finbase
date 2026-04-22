"""
Pin IndexDB's dependency on a bare ``sqlite3.Connection`` rather than the
full ``TimeSeriesDB`` instance.

Before this fix IndexDB reached into ``self.db.conn`` on every method,
silently coupling to TimeSeriesDB's private attribute. A change to
TimeSeriesDB's connection handling would have broken every index call
path without any test catching it. The cleaner boundary — pass the
connection — is enforced here.
"""

import sqlite3

import pandas as pd
import pytest

from finbase.data.database.index_db import IndexDB


class TestIndexDBAcceptsConnection:
    """Construction with a plain sqlite3.Connection must work."""

    def test_accepts_sqlite_connection_directly(self, test_db):
        idb = IndexDB(test_db.conn)
        assert idb.get_index_id("SP500") is None  # smoke

    def test_register_index_via_connection(self, test_db):
        idb = IndexDB(test_db.conn)
        index_id = idb.register_index(
            index_code="DOW30",
            index_name="Dow Jones Industrial Average",
            description="Blue chip US stocks",
            country="US",
            data_source="wikipedia",
        )
        assert isinstance(index_id, int)
        assert index_id > 0

    def test_update_constituents_via_connection(self, test_db):
        idb = IndexDB(test_db.conn)
        idb.register_index("SP500", "S&P 500", "desc", "US", "wikipedia")
        df = pd.DataFrame(
            {
                "symbol": ["AAPL", "MSFT"],
                "company_name": ["Apple", "Microsoft"],
                "sector": ["Technology", "Technology"],
                "source": ["wikipedia", "wikipedia"],
            }
        )
        result = idb.update_constituents("SP500", df)
        assert result["added_count"] == 2


class TestIndexDBBackwardCompat:
    """Existing ``IndexDB(TimeSeriesDB)`` call sites must keep working.

    Changing this signature is a code smell magnet: every caller (including
    external consumers of DataClient's index methods) would have to move
    in lockstep. We accept either shape, detect it, and document the
    connection form as preferred going forward.
    """

    def test_still_accepts_timeseries_db_instance(self, test_db):
        idb = IndexDB(test_db)
        assert idb.get_index_id("SP500") is None

    def test_methods_work_with_timeseries_db_shape(self, test_db):
        idb = IndexDB(test_db)
        index_id = idb.register_index(
            "NDX", "NASDAQ-100", "desc", "US", "wikipedia"
        )
        assert index_id > 0
        assert idb.get_index_id("NDX") == index_id
