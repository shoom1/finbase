"""Unit tests for TimeSeriesDB class."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from finbase.data.database.timeseries_db import (
    TimeSeriesDB,
    DatabaseError,
    ValidationError
)


class TestTimeSeriesDBInit:
    """Test database initialization."""

    def test_init_creates_db_file(self, temp_db_path):
        """Test that database file is created."""
        db = TimeSeriesDB(temp_db_path)
        assert db.db_path.parent.exists()
        assert db.conn is not None
        db.close()

    def test_context_manager(self, temp_db_path):
        """Test that context manager works correctly."""
        with TimeSeriesDB(temp_db_path) as db:
            assert db.conn is not None

        # Connection should be closed after exiting context
        with pytest.raises(Exception):
            db.conn.execute("SELECT 1")

    def test_initialize_schema(self, test_db):
        """Test schema initialization."""
        # Schema should already be initialized by fixture
        cursor = test_db.conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert 'risk_factors' in tables
        assert 'timeseries_data' in tables
        assert 'data_updates' in tables


class TestAddRiskFactor:
    """Test add_risk_factor method."""

    def test_add_valid_risk_factor(self, test_db):
        """Test adding a valid risk factor."""
        rf_id = test_db.add_risk_factor(
            symbol='AAPL',
            asset_class='equity',
            data_source='yfinance',
            frequency='daily',
            description='Apple Inc.'
        )

        assert isinstance(rf_id, int)
        assert rf_id > 0

    def test_add_risk_factor_with_metadata(self, test_db):
        """Test adding risk factor with metadata."""
        metadata = {'exchange': 'NASDAQ', 'sector_code': '45'}

        rf_id = test_db.add_risk_factor(
            symbol='AAPL',
            asset_class='equity',
            data_source='yfinance',
            metadata=metadata
        )

        # Retrieve and verify
        info = test_db.get_risk_factor_info('AAPL', 'yfinance')
        assert info is not None
        assert 'NASDAQ' in info['metadata_json']

    def test_add_duplicate_risk_factor(self, test_db):
        """Test that adding duplicate returns existing ID."""
        rf_id1 = test_db.add_risk_factor(
            symbol='AAPL',
            asset_class='equity',
            data_source='yfinance'
        )

        rf_id2 = test_db.add_risk_factor(
            symbol='AAPL',
            asset_class='equity',
            data_source='yfinance'
        )

        assert rf_id1 == rf_id2

    def test_add_risk_factor_empty_symbol(self, test_db):
        """Test validation for empty symbol."""
        with pytest.raises(ValidationError, match="Symbol must be a non-empty string"):
            test_db.add_risk_factor(
                symbol='',
                asset_class='equity',
                data_source='yfinance'
            )

    def test_add_risk_factor_invalid_asset_class(self, test_db):
        """Test validation for invalid asset class."""
        with pytest.raises(ValidationError, match="Invalid asset class"):
            test_db.add_risk_factor(
                symbol='TEST',
                asset_class='invalid_class',
                data_source='yfinance'
            )

    def test_add_risk_factor_invalid_frequency(self, test_db):
        """Test validation for invalid frequency."""
        with pytest.raises(ValidationError, match="Invalid frequency"):
            test_db.add_risk_factor(
                symbol='TEST',
                asset_class='equity',
                data_source='yfinance',
                frequency='invalid_freq'
            )

    def test_add_risk_factor_none_symbol(self, test_db):
        """Test validation for None symbol."""
        with pytest.raises(ValidationError):
            test_db.add_risk_factor(
                symbol=None,
                asset_class='equity',
                data_source='yfinance'
            )


class TestAddTimeseriesData:
    """Test add_timeseries_data method."""

    def test_add_valid_timeseries_data(self, test_db, sample_risk_factor_data, sample_ohlcv_data):
        """Test adding valid timeseries data."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        records_added = test_db.add_timeseries_data(
            risk_factor_id=rf_id,
            data=sample_ohlcv_data
        )

        assert records_added == len(sample_ohlcv_data)

    def test_add_timeseries_with_date_index(self, test_db, sample_risk_factor_data, sample_ohlcv_data_with_index):
        """Test adding data with date as index."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        records_added = test_db.add_timeseries_data(
            risk_factor_id=rf_id,
            data=sample_ohlcv_data_with_index
        )

        assert records_added > 0

    def test_add_timeseries_skips_nan_close(self, test_db, sample_risk_factor_data):
        """Test that rows with NaN close prices are skipped."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'close': [100, np.nan, 102, np.nan, 104],
            'adj_close': [100, 101, 102, 103, 104]
        })

        records_added = test_db.add_timeseries_data(rf_id, data)

        # Should only add 3 records (skipping 2 NaN)
        assert records_added == 3

    def test_add_timeseries_invalid_risk_factor_id(self, test_db, sample_ohlcv_data):
        """Test validation for invalid risk_factor_id."""
        with pytest.raises(ValidationError, match="risk_factor_id must be a positive integer"):
            test_db.add_timeseries_data(
                risk_factor_id=0,
                data=sample_ohlcv_data
            )

    def test_add_timeseries_empty_dataframe(self, test_db, sample_risk_factor_data):
        """Test validation for empty DataFrame."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        with pytest.raises(ValidationError, match="Data cannot be None or empty"):
            test_db.add_timeseries_data(
                risk_factor_id=rf_id,
                data=pd.DataFrame()
            )

    def test_add_timeseries_missing_close_column(self, test_db, sample_risk_factor_data):
        """Test validation for missing close column."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'open': [100, 101, 102, 103, 104]
        })

        with pytest.raises(ValidationError, match="Close column .* not found"):
            test_db.add_timeseries_data(rf_id, data)

    def test_add_timeseries_all_nan_close(self, test_db, sample_risk_factor_data):
        """Test validation when all close prices are NaN."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=5),
            'close': [np.nan] * 5
        })

        with pytest.raises(ValidationError, match="No valid records to insert"):
            test_db.add_timeseries_data(rf_id, data)

    def test_add_timeseries_updates_metadata(self, test_db, sample_risk_factor_data, sample_ohlcv_data):
        """Test that risk factor metadata is updated after adding data."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        test_db.add_timeseries_data(rf_id, sample_ohlcv_data)

        info = test_db.get_risk_factor_info(sample_risk_factor_data['symbol'], sample_risk_factor_data['data_source'])

        assert info['start_date'] is not None
        assert info['end_date'] is not None
        assert info['last_updated'] is not None


class TestQuery:
    """Test query method."""

    def test_query_single_symbol(self, populated_db, sample_risk_factor_data):
        """Test querying data for a single symbol."""
        result = populated_db.query(
            symbols=[sample_risk_factor_data['symbol']],
            start_date='2024-01-01',
            end_date='2024-01-31',
            column='adj_close',
            data_source=sample_risk_factor_data['data_source']
        )

        assert isinstance(result, pd.DataFrame)
        assert sample_risk_factor_data['symbol'] in result.columns
        assert len(result) > 0

    def test_query_multiple_symbols(self, multiple_symbols_db):
        """Test querying data for multiple symbols."""
        result = multiple_symbols_db.query(
            symbols=['AAPL', 'MSFT', 'JPM'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            column='adj_close'
        )

        assert isinstance(result, pd.DataFrame)
        assert 'AAPL' in result.columns
        assert 'MSFT' in result.columns
        assert 'JPM' in result.columns

    def test_query_different_columns(self, populated_db, sample_risk_factor_data):
        """Test querying different columns."""
        for column in ['open', 'high', 'low', 'close', 'adj_close', 'volume']:
            result = populated_db.query(
                symbols=[sample_risk_factor_data['symbol']],
                start_date='2024-01-01',
                end_date='2024-01-31',
                column=column,
                data_source=sample_risk_factor_data['data_source']
            )

            assert isinstance(result, pd.DataFrame)
            assert len(result) > 0

    def test_query_invalid_column(self, populated_db):
        """Test validation for invalid column."""
        with pytest.raises(ValidationError, match="Invalid column"):
            populated_db.query(
                symbols=['TEST'],
                start_date='2024-01-01',
                end_date='2024-01-31',
                column='invalid_column'
            )

    def test_query_empty_symbols_list(self, populated_db):
        """Test validation for empty symbols list."""
        with pytest.raises(ValidationError, match="Symbols must be a non-empty list"):
            populated_db.query(
                symbols=[],
                start_date='2024-01-01',
                end_date='2024-01-31'
            )

    def test_query_invalid_date_format(self, populated_db, sample_risk_factor_data):
        """Test validation for invalid date format."""
        with pytest.raises(ValidationError, match="Invalid start_date format"):
            populated_db.query(
                symbols=[sample_risk_factor_data['symbol']],
                start_date='not-a-date',  # Invalid date
                end_date='2024-01-31',
                data_source=sample_risk_factor_data['data_source']
            )

    def test_query_invalid_end_date_format(self, populated_db, sample_risk_factor_data):
        """Symmetric check for the end_date validation message."""
        with pytest.raises(ValidationError, match="Invalid end_date format"):
            populated_db.query(
                symbols=[sample_risk_factor_data['symbol']],
                start_date='2024-01-01',
                end_date='not-a-date',
                data_source=sample_risk_factor_data['data_source']
            )

    def test_query_nonexistent_symbol(self, test_db):
        """Test querying non-existent symbol."""
        with pytest.raises(DatabaseError, match="No risk factors found"):
            test_db.query(
                symbols=['NONEXISTENT'],
                start_date='2024-01-01',
                end_date='2024-01-31'
            )


class TestGetRiskFactorInfo:
    """Test get_risk_factor_info method."""

    def test_get_existing_risk_factor(self, populated_db, sample_risk_factor_data):
        """Test getting info for existing risk factor."""
        info = populated_db.get_risk_factor_info(
            sample_risk_factor_data['symbol'],
            sample_risk_factor_data['data_source']
        )

        assert info is not None
        assert info['symbol'] == sample_risk_factor_data['symbol']
        assert info['asset_class'] == sample_risk_factor_data['asset_class']

    def test_get_nonexistent_risk_factor(self, test_db):
        """Test getting info for non-existent risk factor."""
        info = test_db.get_risk_factor_info('NONEXISTENT', 'yfinance')

        assert info is None


class TestListRiskFactors:
    """Test list_risk_factors method."""

    def test_list_all_risk_factors(self, multiple_symbols_db):
        """Test listing all risk factors."""
        df = multiple_symbols_db.list_risk_factors()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3

    def test_list_risk_factors_by_asset_class(self, multiple_symbols_db):
        """Test filtering by asset class."""
        df = multiple_symbols_db.list_risk_factors(asset_class='equity')

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert all(df['asset_class'] == 'equity')

    def test_list_risk_factors_by_sector(self, multiple_symbols_db):
        """Test filtering by sector."""
        df = multiple_symbols_db.list_risk_factors(sector='Technology')

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2  # AAPL and MSFT


class TestCountTimeseriesRows:
    """Test count_timeseries_rows method."""

    def test_empty_db_returns_zero(self, test_db):
        """Empty database returns 0 rows."""
        assert test_db.count_timeseries_rows() == 0

    def test_populated_db_returns_actual_count(self, populated_db, sample_ohlcv_data):
        """Populated database returns the actual row count from timeseries_data."""
        assert populated_db.count_timeseries_rows() == len(sample_ohlcv_data)

    def test_multiple_symbols_sums_all_rows(self, multiple_symbols_db):
        """Count covers all symbols, not just one."""
        # multiple_symbols_db loads 3 symbols, each with the same business-day range
        expected_rows_per_symbol = len(
            pd.date_range(start='2024-01-01', end='2024-01-31', freq='B')
        )
        assert multiple_symbols_db.count_timeseries_rows() == 3 * expected_rows_per_symbol


class TestGetTimeseriesDateBounds:
    """Test get_timeseries_date_bounds method."""

    def test_empty_db_returns_none_tuple(self, test_db):
        """Empty database returns (None, None)."""
        assert test_db.get_timeseries_date_bounds() == (None, None)

    def test_populated_db_returns_actual_bounds(self, populated_db, sample_ohlcv_data):
        """Populated database returns min/max dates matching inserted data."""
        min_date, max_date = populated_db.get_timeseries_date_bounds()
        expected_min = sample_ohlcv_data['date'].min().strftime('%Y-%m-%d')
        expected_max = sample_ohlcv_data['date'].max().strftime('%Y-%m-%d')
        assert min_date == expected_min
        assert max_date == expected_max


class TestGetLatestUpdateTimestamp:
    """Test get_latest_update_timestamp method."""

    def test_empty_db_returns_none(self, test_db):
        """Empty database returns None."""
        assert test_db.get_latest_update_timestamp() is None

    def test_populated_db_returns_timestamp(self, populated_db):
        """Populated database returns a non-None timestamp string."""
        ts = populated_db.get_latest_update_timestamp()
        assert ts is not None
        # Should parse as a datetime
        parsed = pd.to_datetime(ts)
        assert parsed is not pd.NaT


class TestGetCoverageSummary:
    """Test get_coverage_summary method."""

    def test_empty_db_returns_empty_dataframe(self, test_db):
        """Empty database returns an empty DataFrame (with expected columns)."""
        df = test_db.get_coverage_summary()
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_populated_db_has_expected_columns(self, multiple_symbols_db):
        """Coverage summary has the columns the dashboard expects."""
        df = multiple_symbols_db.get_coverage_summary()
        expected = {
            'symbol', 'asset_class', 'sector',
            'start_date', 'end_date',
            'data_points', 'actual_start', 'actual_end',
        }
        assert expected.issubset(set(df.columns))

    def test_populated_db_one_row_per_symbol(self, multiple_symbols_db):
        """Each active symbol produces exactly one row (GROUP BY risk_factor_id)."""
        df = multiple_symbols_db.get_coverage_summary()
        assert len(df) == 3
        assert set(df['symbol']) == {'AAPL', 'MSFT', 'JPM'}

    def test_populated_db_data_points_nonzero(self, multiple_symbols_db):
        """data_points reflects the LEFT JOIN count, not zero."""
        df = multiple_symbols_db.get_coverage_summary()
        assert (df['data_points'] > 0).all()

    def test_inactive_risk_factors_excluded(self, test_db, sample_risk_factor_data, sample_ohlcv_data):
        """Soft-deleted (is_active=0) risk factors are not returned."""
        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)
        test_db.add_timeseries_data(rf_id, sample_ohlcv_data)

        # Soft delete
        test_db.conn.execute(
            "UPDATE risk_factors SET is_active = 0 WHERE risk_factor_id = ?",
            (rf_id,),
        )
        test_db.conn.commit()

        df = test_db.get_coverage_summary()
        assert df.empty


class TestBulkInsertion:
    """Test that bulk insertion is more efficient than row-by-row."""

    def test_bulk_insertion_performance(self, test_db, sample_risk_factor_data):
        """Test that bulk insertion completes successfully with large dataset."""
        import time

        rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

        # Create larger dataset
        dates = pd.date_range(start='2020-01-01', end='2024-12-31', freq='B')
        n = len(dates)

        data = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(100, 110, n),
            'high': np.random.uniform(110, 120, n),
            'low': np.random.uniform(90, 100, n),
            'close': np.random.uniform(100, 110, n),
            'adj_close': np.random.uniform(100, 110, n),
            'volume': np.random.randint(1000000, 10000000, n)
        })

        start_time = time.time()
        records_added = test_db.add_timeseries_data(rf_id, data)
        elapsed = time.time() - start_time

        # Should complete in reasonable time (< 5 seconds for ~1300 records)
        assert elapsed < 5.0
        assert records_added == len(data)
        print(f"\nBulk insert: {records_added} records in {elapsed:.2f}s ({records_added/elapsed:.0f} records/sec)")
