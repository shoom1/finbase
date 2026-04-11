"""Tests for IndexDB - index constituent management."""

import pytest
import pandas as pd
from datetime import date, datetime

from finbase.data.database.index_db import IndexDB
from finbase.data.database.timeseries_db import DatabaseError


class TestRegisterIndex:

    def test_register_new_index(self, index_db):
        index_id = index_db.register_index(
            index_code='DOW30',
            index_name='Dow Jones Industrial Average',
            description='Blue chip US stocks',
            country='US',
            data_source='wikipedia',
        )
        assert isinstance(index_id, int)
        assert index_id > 0

    def test_register_existing_index_returns_same_id(self, index_db):
        id1 = index_db.register_index('DOW30', 'Dow 30', 'desc', 'US', 'wikipedia')
        id2 = index_db.register_index('DOW30', 'Dow 30 Updated', 'new desc', 'US', 'wikipedia')
        assert id1 == id2

    def test_get_index_id(self, index_db):
        index_db.register_index('NDX', 'NASDAQ-100', 'desc', 'US', 'wikipedia')
        assert index_db.get_index_id('NDX') is not None

    def test_get_index_id_not_found(self, index_db):
        assert index_db.get_index_id('NONEXISTENT') is None


class TestUpdateConstituents:

    def test_initial_load(self, index_db, sample_constituents_df):
        index_db.register_index('SP500', 'S&P 500', 'desc', 'US', 'wikipedia')
        result = index_db.update_constituents('SP500', sample_constituents_df)
        assert result['added_count'] == 5
        assert result['removed_count'] == 0
        assert result['unchanged_count'] == 0

    def test_no_changes_on_same_data(self, populated_index_db, sample_constituents_df):
        result = populated_index_db.update_constituents('SP500', sample_constituents_df)
        assert result['added_count'] == 0
        assert result['removed_count'] == 0
        assert result['unchanged_count'] == 5

    def test_detects_additions(self, populated_index_db, sample_constituents_df):
        new_df = pd.concat([
            sample_constituents_df,
            pd.DataFrame({
                'symbol': ['NVDA'],
                'company_name': ['NVIDIA Corp.'],
                'sector': ['Technology'],
                'sub_industry': ['Semiconductors'],
                'source': ['wikipedia'],
            })
        ], ignore_index=True)
        result = populated_index_db.update_constituents('SP500', new_df)
        assert result['added_count'] == 1
        assert 'NVDA' in result['added_symbols']

    def test_detects_removals(self, populated_index_db):
        smaller_df = pd.DataFrame({
            'symbol': ['AAPL', 'MSFT', 'GOOGL'],
            'company_name': ['Apple', 'Microsoft', 'Alphabet'],
            'sector': ['Tech', 'Tech', 'Comms'],
            'source': ['wikipedia'] * 3,
        })
        result = populated_index_db.update_constituents('SP500', smaller_df)
        assert result['removed_count'] == 2
        assert set(result['removed_symbols']) == {'AMZN', 'META'}

    def test_update_unregistered_index_raises(self, index_db, sample_constituents_df):
        with pytest.raises(DatabaseError, match="not registered"):
            index_db.update_constituents('FAKE', sample_constituents_df)


class TestQueryConstituents:

    def test_get_current_constituents(self, populated_index_db):
        df = populated_index_db.get_current_constituents('SP500')
        assert len(df) == 5
        assert 'AAPL' in df['symbol'].values

    def test_get_current_constituents_empty_index(self, index_db):
        index_db.register_index('EMPTY', 'Empty Index', 'desc', 'US', 'wikipedia')
        df = index_db.get_current_constituents('EMPTY')
        assert df.empty

    def test_get_historical_constituents(self, index_db, sample_constituents_df):
        # Register and load constituents with an explicit past effective_date
        index_db.register_index('SP500', 'S&P 500', 'desc', 'US', 'wikipedia')
        index_db.update_constituents(
            'SP500', sample_constituents_df, effective_date=date(2024, 1, 1)
        )
        # Remove some with a later effective_date
        smaller_df = pd.DataFrame({
            'symbol': ['AAPL', 'MSFT'],
            'company_name': ['Apple', 'Microsoft'],
            'sector': ['Tech', 'Tech'],
            'source': ['wikipedia'] * 2,
        })
        index_db.update_constituents(
            'SP500', smaller_df, effective_date=date(2024, 6, 1)
        )
        # As of before removal, should still have all 5
        df = index_db.get_historical_constituents('SP500', '2024-03-01')
        assert len(df) == 5

    def test_is_index_member_true(self, populated_index_db):
        assert populated_index_db.is_index_member('AAPL', 'SP500') is True

    def test_is_index_member_false(self, populated_index_db):
        assert populated_index_db.is_index_member('TSLA', 'SP500') is False

    def test_list_indices(self, populated_index_db):
        df = populated_index_db.list_indices()
        assert len(df) == 1
        assert df.iloc[0]['index_code'] == 'SP500'


class TestGetIndexChanges:

    def test_get_changes_after_removal(self, populated_index_db):
        smaller_df = pd.DataFrame({
            'symbol': ['AAPL', 'MSFT', 'GOOGL'],
            'company_name': ['Apple', 'Microsoft', 'Alphabet'],
            'sector': ['Tech', 'Tech', 'Comms'],
            'source': ['wikipedia'] * 3,
        })
        populated_index_db.update_constituents(
            'SP500', smaller_df, effective_date=date(2025, 6, 1)
        )
        changes = populated_index_db.get_index_changes('SP500')
        assert not changes.empty
        removed = changes[changes['change_type'] == 'removed']
        assert len(removed) == 2
