"""
Unit tests for DataClient API.

Tests all public methods of the DataClient class with mocked database.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from finbase.client.client import DataClient
from finbase.data.database import DatabaseError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_path(tmp_path):
    """Create a temporary database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_timeseries_data():
    """Create sample timeseries data for testing."""
    dates = pd.date_range('2024-01-01', '2024-01-10', freq='D')
    data = {
        'AAPL': [150 + i for i in range(len(dates))],
        'MSFT': [250 + i for i in range(len(dates))],
        'GOOGL': [100 + i for i in range(len(dates))]
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'date'
    return df


@pytest.fixture
def sample_risk_factors():
    """Create sample risk factor metadata."""
    return pd.DataFrame([
        {
            'symbol': 'AAPL',
            'asset_class': 'equity',
            'asset_subclass': 'stock',
            'description': 'Apple Inc.',
            'country': 'US',
            'currency': 'USD',
            'sector': 'Technology',
            'data_source': 'yfinance',
            'frequency': 'daily',
            'start_date': '2020-01-01',
            'end_date': '2024-01-10'
        },
        {
            'symbol': 'MSFT',
            'asset_class': 'equity',
            'asset_subclass': 'stock',
            'description': 'Microsoft Corporation',
            'country': 'US',
            'currency': 'USD',
            'sector': 'Technology',
            'data_source': 'yfinance',
            'frequency': 'daily',
            'start_date': '2020-01-01',
            'end_date': '2024-01-10'
        },
        {
            'symbol': 'GOOGL',
            'asset_class': 'equity',
            'asset_subclass': 'stock',
            'description': 'Alphabet Inc.',
            'country': 'US',
            'currency': 'USD',
            'sector': 'Technology',
            'data_source': 'yfinance',
            'frequency': 'daily',
            'start_date': '2020-01-01',
            'end_date': '2024-01-10'
        },
        {
            'symbol': 'JPM',
            'asset_class': 'equity',
            'asset_subclass': 'stock',
            'description': 'JPMorgan Chase & Co.',
            'country': 'US',
            'currency': 'USD',
            'sector': 'Finance',
            'data_source': 'yfinance',
            'frequency': 'daily',
            'start_date': '2020-01-01',
            'end_date': '2024-01-10'
        }
    ])


@pytest.fixture
def mock_db(sample_timeseries_data, sample_risk_factors):
    """Create a mock TimeSeriesDB."""
    mock = MagicMock()

    # Mock query() to return sample data
    def mock_query(symbols, start_date=None, end_date=None, column='close', data_source='yfinance'):
        df = sample_timeseries_data.copy()

        # Filter by symbols
        available_symbols = [s for s in symbols if s in df.columns]
        if available_symbols:
            df = df[available_symbols]
        else:
            df = pd.DataFrame()

        # Filter by date range - convert strings to datetime for comparison
        if start_date:
            start_dt = pd.to_datetime(start_date)
            df = df[df.index >= start_dt]
        if end_date:
            end_dt = pd.to_datetime(end_date)
            df = df[df.index <= end_dt]

        return df

    mock.query.side_effect = mock_query

    # Mock list_risk_factors()
    def mock_list_risk_factors(asset_class=None, country=None, sector=None):
        df = sample_risk_factors.copy()

        if asset_class:
            df = df[df['asset_class'] == asset_class]
        if country:
            df = df[df['country'] == country]
        if sector:
            df = df[df['sector'] == sector]

        return df

    mock.list_risk_factors.side_effect = mock_list_risk_factors

    # Mock get_risk_factor_info()
    def mock_get_risk_factor_info(symbol, data_source='yfinance'):
        matches = sample_risk_factors[
            (sample_risk_factors['symbol'] == symbol) &
            (sample_risk_factors['data_source'] == data_source)
        ]
        if not matches.empty:
            return matches.iloc[0].to_dict()
        return None

    mock.get_risk_factor_info.side_effect = mock_get_risk_factor_info

    # Make it work as context manager
    mock.__enter__ = Mock(return_value=mock)
    mock.__exit__ = Mock(return_value=False)

    return mock


@pytest.fixture
def client(mock_db_path):
    """Create a DataClient instance."""
    return DataClient(db_path=mock_db_path)


# ============================================================================
# Test Initialization
# ============================================================================

class TestInitialization:
    """Test DataClient initialization."""

    def test_init_with_explicit_path(self, mock_db_path):
        """Test initialization with explicit database path."""
        client = DataClient(db_path=mock_db_path)
        assert client.db_path == mock_db_path

    @patch('finbase.client.client.get_settings')
    def test_init_without_path(self, mock_settings):
        """Test initialization without explicit path (uses settings)."""
        mock_settings.return_value.database.path = '/default/path.db'
        client = DataClient()
        assert client.db_path == '/default/path.db'


# ============================================================================
# Test get_data() - Core Method
# ============================================================================

class TestGetData:
    """Test get_data() method."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_single_symbol_long_format(self, mock_db_class, client, mock_db):
        """Test getting data for single symbol in long format."""
        mock_db_class.return_value = mock_db

        df = client.get_data('AAPL', columns=['close'], start='2024-01-01', end='2024-01-05')

        # Check structure
        assert not df.empty
        assert list(df.columns) == ['date', 'symbol', 'data_source', 'metric', 'value']

        # Check content
        assert (df['symbol'] == 'AAPL').all()
        assert (df['metric'] == 'close').all()
        assert (df['data_source'] == 'yfinance').all()
        assert len(df) == 5  # 5 days

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_multiple_symbols_long_format(self, mock_db_class, client, mock_db):
        """Test getting data for multiple symbols in long format."""
        mock_db_class.return_value = mock_db

        df = client.get_data(['AAPL', 'MSFT'], columns=['close'],
                           start='2024-01-01', end='2024-01-03')

        assert not df.empty
        assert set(df['symbol'].unique()) == {'AAPL', 'MSFT'}
        assert len(df) == 6  # 3 days × 2 symbols

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_wide_format(self, mock_db_class, client, mock_db):
        """Test getting data in wide format."""
        mock_db_class.return_value = mock_db

        df = client.get_data(['AAPL', 'MSFT'], columns=['close'],
                           start='2024-01-01', end='2024-01-03',
                           format='wide')

        assert not df.empty
        assert isinstance(df.index, pd.MultiIndex)
        assert df.index.names == ['date', 'symbol']
        assert 'close' in df.columns

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_multiple_columns(self, mock_db_class, client, mock_db):
        """Test getting multiple columns."""
        mock_db_class.return_value = mock_db

        df = client.get_data('AAPL', columns=['close', 'volume'],
                           start='2024-01-01', end='2024-01-03')

        assert not df.empty
        # Should have 2 metrics × 3 days = 6 rows
        assert set(df['metric'].unique()) == {'close', 'volume'}

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_all_columns_default(self, mock_db_class, client, mock_db):
        """Test getting all OHLCV columns by default."""
        mock_db_class.return_value = mock_db

        df = client.get_data('AAPL', start='2024-01-01', end='2024-01-02')

        assert not df.empty
        expected_metrics = {'open', 'high', 'low', 'close', 'adj_close', 'volume'}
        assert set(df['metric'].unique()) == expected_metrics

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_invalid_column(self, mock_db_class, client, mock_db):
        """Test error handling for invalid column."""
        mock_db_class.return_value = mock_db

        with pytest.raises(ValueError, match="Invalid columns"):
            client.get_data('AAPL', columns=['invalid_column'])

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_no_data_returns_empty(self, mock_db_class, client):
        """Test that no data returns empty DataFrame with correct schema."""
        # Mock DB that returns empty DataFrame
        empty_mock = MagicMock()
        empty_mock.query.return_value = pd.DataFrame()
        empty_mock.__enter__ = Mock(return_value=empty_mock)
        empty_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = empty_mock

        df = client.get_data('NONEXISTENT', columns=['close'])

        assert df.empty
        assert list(df.columns) == ['date', 'symbol', 'data_source', 'metric', 'value']


# ============================================================================
# Test Convenience Methods
# ============================================================================

class TestConvenienceMethods:
    """Test convenience methods."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_closes(self, mock_db_class, client, mock_db):
        """Test get_closes() convenience method."""
        mock_db_class.return_value = mock_db

        df = client.get_closes(['AAPL', 'MSFT'], start='2024-01-01', end='2024-01-05')

        assert not df.empty
        assert 'AAPL' in df.columns
        assert 'MSFT' in df.columns
        assert df.index.name == 'date'

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_closes_single_symbol(self, mock_db_class, client, mock_db):
        """Test get_closes() with single symbol."""
        mock_db_class.return_value = mock_db

        df = client.get_closes('AAPL', start='2024-01-01', end='2024-01-05')

        assert not df.empty
        assert 'AAPL' in df.columns

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_latest(self, mock_db_class, client, mock_db):
        """Test get_latest() method."""
        mock_db_class.return_value = mock_db

        with patch('finbase.client.client.datetime') as mock_datetime:
            # Mock current date
            mock_datetime.now.return_value = datetime(2024, 1, 10)
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            df = client.get_latest('AAPL', days=5, columns=['close'])

            assert not df.empty
            assert (df['symbol'] == 'AAPL').all()
            assert (df['metric'] == 'close').all()

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_all(self, mock_db_class, client, mock_db):
        """Test get_all() method."""
        mock_db_class.return_value = mock_db

        df = client.get_all('AAPL', columns=['close'])

        assert not df.empty
        assert (df['symbol'] == 'AAPL').all()
        assert (df['metric'] == 'close').all()


# ============================================================================
# Test Discovery Methods
# ============================================================================

class TestDiscoveryMethods:
    """Test discovery methods."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_list_symbols_all(self, mock_db_class, client, mock_db):
        """Test listing all symbols."""
        mock_db_class.return_value = mock_db

        symbols = client.list_symbols()

        assert isinstance(symbols, list)
        assert 'AAPL' in symbols
        assert 'MSFT' in symbols
        assert 'GOOGL' in symbols
        assert 'JPM' in symbols

    @patch('finbase.client.client.TimeSeriesDB')
    def test_list_symbols_with_filters(self, mock_db_class, client, mock_db):
        """Test listing symbols with filters."""
        mock_db_class.return_value = mock_db

        symbols = client.list_symbols(asset_class='equity', sector='Technology')

        assert isinstance(symbols, list)
        assert 'AAPL' in symbols
        assert 'MSFT' in symbols
        assert 'GOOGL' in symbols
        assert 'JPM' not in symbols  # Finance sector

    @patch('finbase.client.client.TimeSeriesDB')
    def test_list_symbols_empty_result(self, mock_db_class, client):
        """Test listing symbols with no matches."""
        empty_mock = MagicMock()
        empty_mock.list_risk_factors.return_value = pd.DataFrame()
        empty_mock.__enter__ = Mock(return_value=empty_mock)
        empty_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = empty_mock

        symbols = client.list_symbols(sector='NonexistentSector')

        assert symbols == []

    @patch('finbase.client.client.TimeSeriesDB')
    def test_search_symbols_with_pattern(self, mock_db_class, client, mock_db):
        """Test searching symbols with pattern."""
        mock_db_class.return_value = mock_db

        df = client.search_symbols(pattern='A*')

        assert not df.empty
        assert 'AAPL' in df['symbol'].values
        # Pattern matching is case-insensitive

    @patch('finbase.client.client.TimeSeriesDB')
    def test_search_symbols_with_filters(self, mock_db_class, client, mock_db):
        """Test searching symbols with filters and pattern."""
        mock_db_class.return_value = mock_db

        df = client.search_symbols(pattern='*', sector='Technology')

        assert not df.empty
        assert (df['sector'] == 'Technology').all()


# ============================================================================
# Test Metadata Methods
# ============================================================================

class TestMetadataMethods:
    """Test metadata methods."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_symbol_info_exists(self, mock_db_class, client, mock_db):
        """Test getting info for existing symbol."""
        mock_db_class.return_value = mock_db

        info = client.get_symbol_info('AAPL')

        assert info is not None
        assert info['symbol'] == 'AAPL'
        assert info['description'] == 'Apple Inc.'
        assert info['asset_class'] == 'equity'
        assert info['sector'] == 'Technology'
        assert info['data_source'] == 'yfinance'

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_symbol_info_not_exists(self, mock_db_class, client, mock_db):
        """Test getting info for non-existent symbol."""
        mock_db_class.return_value = mock_db

        info = client.get_symbol_info('NONEXISTENT')

        assert info is None

    @patch('finbase.client.client.TimeSeriesDB')
    def test_has_symbol_true(self, mock_db_class, client, mock_db):
        """Test has_symbol() for existing symbol."""
        mock_db_class.return_value = mock_db

        assert client.has_symbol('AAPL') is True

    @patch('finbase.client.client.TimeSeriesDB')
    def test_has_symbol_false(self, mock_db_class, client, mock_db):
        """Test has_symbol() for non-existent symbol."""
        mock_db_class.return_value = mock_db

        assert client.has_symbol('NONEXISTENT') is False

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_date_range_exists(self, mock_db_class, client, mock_db):
        """Test getting date range for existing symbol."""
        mock_db_class.return_value = mock_db

        start, end = client.get_date_range('AAPL')

        assert start == '2020-01-01'
        assert end == '2024-01-10'

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_date_range_not_exists(self, mock_db_class, client, mock_db):
        """Test getting date range for non-existent symbol."""
        mock_db_class.return_value = mock_db

        result = client.get_date_range('NONEXISTENT')

        assert result is None


# ============================================================================
# Test Statistics and Bulk Methods
# ============================================================================

class TestStatisticsAndBulkMethods:
    """Test statistics and bulk retrieval methods."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_stats(self, mock_db_class, client, mock_db):
        """Test get_stats() method."""
        mock_db_class.return_value = mock_db

        stats = client.get_stats()

        assert isinstance(stats, dict)
        assert 'total_symbols' in stats
        assert stats['total_symbols'] == 4
        assert 'asset_classes' in stats
        assert 'equity' in stats['asset_classes']
        assert 'data_sources' in stats
        assert 'yfinance' in stats['data_sources']
        assert 'date_range' in stats
        assert 'by_asset_class' in stats

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_stats_empty_db(self, mock_db_class, client):
        """Test get_stats() with empty database."""
        empty_mock = MagicMock()
        empty_mock.list_risk_factors.return_value = pd.DataFrame()
        empty_mock.__enter__ = Mock(return_value=empty_mock)
        empty_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = empty_mock

        stats = client.get_stats()

        assert stats['total_symbols'] == 0
        assert stats['asset_classes'] == []
        assert stats['data_sources'] == []

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_by_asset_class(self, mock_db_class, client, mock_db):
        """Test get_by_asset_class() method."""
        mock_db_class.return_value = mock_db

        df = client.get_by_asset_class('equity', columns=['close'],
                                       start='2024-01-01', end='2024-01-03')

        assert not df.empty
        # Only symbols with data are returned (JPM has no timeseries data in mock)
        assert set(df['symbol'].unique()) == {'AAPL', 'MSFT', 'GOOGL'}

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_by_asset_class_no_symbols(self, mock_db_class, client):
        """Test get_by_asset_class() with no matching symbols."""
        empty_mock = MagicMock()
        empty_mock.list_risk_factors.return_value = pd.DataFrame()
        empty_mock.__enter__ = Mock(return_value=empty_mock)
        empty_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = empty_mock

        df = client.get_by_asset_class('nonexistent')

        assert df.empty
        assert list(df.columns) == ['date', 'symbol', 'data_source', 'metric', 'value']

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_by_sector(self, mock_db_class, client, mock_db):
        """Test get_by_sector() method."""
        mock_db_class.return_value = mock_db

        df = client.get_by_sector('Technology', columns=['close'],
                                 start='2024-01-01', end='2024-01-03')

        assert not df.empty
        # Only tech stocks
        assert set(df['symbol'].unique()) == {'AAPL', 'MSFT', 'GOOGL'}
        assert 'JPM' not in df['symbol'].values

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_by_sector_no_symbols(self, mock_db_class, client):
        """Test get_by_sector() with no matching symbols."""
        empty_mock = MagicMock()
        empty_mock.list_risk_factors.return_value = pd.DataFrame()
        empty_mock.__enter__ = Mock(return_value=empty_mock)
        empty_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = empty_mock

        df = client.get_by_sector('NonexistentSector')

        assert df.empty
        assert list(df.columns) == ['date', 'symbol', 'data_source', 'metric', 'value']


# ============================================================================
# Test Error Conditions and Edge Cases
# ============================================================================

class TestErrorConditionsAndEdgeCases:
    """Test error handling and edge cases."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_database_error_returns_empty(self, mock_db_class, client):
        """Test that DatabaseError (no data found) returns empty DataFrame."""
        error_mock = MagicMock()
        error_mock.query.side_effect = DatabaseError("No risk factors found")
        error_mock.__enter__ = Mock(return_value=error_mock)
        error_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = error_mock

        df = client.get_data('AAPL', columns=['close'])

        assert df.empty
        assert list(df.columns) == ['date', 'symbol', 'data_source', 'metric', 'value']

    @patch('finbase.client.client.TimeSeriesDB')
    def test_get_data_unexpected_error_propagates(self, mock_db_class, client):
        """Test that unexpected exceptions propagate to the caller."""
        error_mock = MagicMock()
        error_mock.query.side_effect = RuntimeError("Unexpected failure")
        error_mock.__enter__ = Mock(return_value=error_mock)
        error_mock.__exit__ = Mock(return_value=False)
        mock_db_class.return_value = error_mock

        with pytest.raises(RuntimeError, match="Unexpected failure"):
            client.get_data('AAPL', columns=['close'])

    def test_get_data_string_symbol_normalized_to_list(self, client, mock_db):
        """Test that single symbol string is normalized to list."""
        with patch('finbase.client.client.TimeSeriesDB', return_value=mock_db):
            df = client.get_data('AAPL', columns=['close'],
                               start='2024-01-01', end='2024-01-03')

            # Should work without error
            assert not df.empty

    @patch('finbase.client.client.TimeSeriesDB')
    def test_wide_format_conversion(self, mock_db_class, client, mock_db):
        """Test that wide format conversion works correctly."""
        mock_db_class.return_value = mock_db

        df = client.get_data(['AAPL', 'MSFT'], columns=['close'],
                           start='2024-01-01', end='2024-01-03',
                           format='wide')

        # Check it's a proper pivot table
        assert isinstance(df.index, pd.MultiIndex)
        assert 'close' in df.columns
        # Should not have 'metric' column name
        assert df.columns.name is None

    @patch('finbase.client.client.TimeSeriesDB')
    def test_data_source_parameter_passed_correctly(self, mock_db_class, client, mock_db):
        """Test that data_source parameter is passed to database queries."""
        mock_db_class.return_value = mock_db

        client.get_data('AAPL', columns=['close'], data_source='bloomberg')

        # Verify query was called with correct data_source
        mock_db.query.assert_called()
        call_kwargs = mock_db.query.call_args[1]
        assert call_kwargs['data_source'] == 'bloomberg'

    @patch('finbase.client.client.TimeSeriesDB')
    def test_empty_symbol_list(self, mock_db_class, client, mock_db):
        """Test handling of empty symbol list."""
        mock_db_class.return_value = mock_db

        df = client.get_data([], columns=['close'])

        # Should return empty DataFrame with correct schema
        assert df.empty
        assert list(df.columns) == ['date', 'symbol', 'data_source', 'metric', 'value']


# ============================================================================
# Test Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Test realistic usage scenarios."""

    @patch('finbase.client.client.TimeSeriesDB')
    def test_portfolio_analysis_workflow(self, mock_db_class, client, mock_db):
        """Test typical portfolio analysis workflow."""
        mock_db_class.return_value = mock_db

        # 1. List available symbols
        symbols = client.list_symbols(asset_class='equity', sector='Technology')
        assert len(symbols) >= 3

        # 2. Get data for portfolio
        portfolio = symbols[:3]
        df = client.get_data(portfolio, columns=['close'],
                           start='2024-01-01', end='2024-01-05')
        assert not df.empty

        # 3. Get in wide format for analysis
        df_wide = client.get_data(portfolio, columns=['close'],
                                 start='2024-01-01', end='2024-01-05',
                                 format='wide')
        assert not df_wide.empty

    @patch('finbase.client.client.TimeSeriesDB')
    def test_data_discovery_workflow(self, mock_db_class, client, mock_db):
        """Test data discovery workflow."""
        mock_db_class.return_value = mock_db

        # 1. Get database statistics
        stats = client.get_stats()
        assert stats['total_symbols'] > 0

        # 2. Check if specific symbol exists
        has_aapl = client.has_symbol('AAPL')
        assert has_aapl is True

        # 3. Get symbol info
        info = client.get_symbol_info('AAPL')
        assert info is not None
        assert 'start_date' in info

        # 4. Get date range
        start, end = client.get_date_range('AAPL')
        assert start is not None
        assert end is not None

    @patch('finbase.client.client.TimeSeriesDB')
    def test_multi_column_multi_symbol_workflow(self, mock_db_class, client, mock_db):
        """Test retrieving multiple columns for multiple symbols."""
        mock_db_class.return_value = mock_db

        df = client.get_data(['AAPL', 'MSFT'],
                           columns=['close', 'volume'],
                           start='2024-01-01', end='2024-01-03')

        assert not df.empty
        # 2 symbols × 2 metrics × 3 days = 12 rows
        assert set(df['symbol'].unique()) == {'AAPL', 'MSFT'}
        assert set(df['metric'].unique()) == {'close', 'volume'}


# ============================================================================
# Test Context Manager Support
# ============================================================================

class TestDataClientContextManager:
    """Tests for DataClient context manager support."""

    def test_context_manager_opens_and_closes(self, temp_db_path):
        """DataClient should work as a context manager."""
        from finbase.data.database import TimeSeriesDB
        with TimeSeriesDB(temp_db_path) as db:
            db.initialize_schema()

        with DataClient(db_path=temp_db_path) as client:
            symbols = client.list_symbols()
            assert isinstance(symbols, list)
        # After exit, the internal DB connection should be closed
        assert client._db is None

    def test_works_without_context_manager(self, temp_db_path):
        """DataClient should still work without 'with' for backward compat."""
        from finbase.data.database import TimeSeriesDB
        with TimeSeriesDB(temp_db_path) as db:
            db.initialize_schema()

        client = DataClient(db_path=temp_db_path)
        symbols = client.list_symbols()
        assert isinstance(symbols, list)
