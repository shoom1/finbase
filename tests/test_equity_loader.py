"""Tests for EquityLoader - YFinance data loading with rate limiting."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime

from finbase.data.loaders.equity_loader import EquityLoader, LoaderError
from finbase.data.database.timeseries_db import TimeSeriesDB, ValidationError


class TestEquityLoaderInit:

    def test_valid_init(self, test_db):
        loader = EquityLoader(test_db, delay_seconds=0, batch_size=5, batch_pause=0)
        assert loader.delay_seconds == 0
        assert loader.batch_size == 5

    def test_invalid_db_type(self):
        with pytest.raises(LoaderError, match="must be a TimeSeriesDB"):
            EquityLoader("not a db")

    def test_negative_delay(self, test_db):
        with pytest.raises(LoaderError, match="non-negative"):
            EquityLoader(test_db, delay_seconds=-1)

    def test_zero_batch_size(self, test_db):
        with pytest.raises(LoaderError, match="positive"):
            EquityLoader(test_db, batch_size=0)

    def test_negative_batch_pause(self, test_db):
        with pytest.raises(LoaderError, match="non-negative"):
            EquityLoader(test_db, batch_pause=-1)

    def test_default_attributes(self, test_db):
        loader = EquityLoader(test_db)
        assert loader.delay_seconds == 5.0
        assert loader.batch_size == 10
        assert loader.batch_pause == 30.0
        assert loader.request_count == 0


class TestLoadSymbol:

    def _make_yf_dataframe(self, periods=5):
        """Create a DataFrame mimicking yfinance output."""
        dates = pd.date_range('2024-01-02', periods=periods, freq='B')
        return pd.DataFrame({
            'Open': [150.0 + i for i in range(periods)],
            'High': [155.0 + i for i in range(periods)],
            'Low': [149.0 + i for i in range(periods)],
            'Close': [153.0 + i for i in range(periods)],
            'Adj Close': [152.0 + i for i in range(periods)],
            'Volume': [1000000 + i * 100000 for i in range(periods)],
        }, index=dates)

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_load_single_symbol(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_yf_dataframe()
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        records = loader.load_symbol(
            symbol='AAPL',
            start_date='2024-01-01',
            end_date='2024-01-31',
        )
        assert records == 5

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_skip_existing_symbol(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_yf_dataframe()
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)

        # Load once
        loader.load_symbol('AAPL', '2024-01-01', '2024-01-31')

        # Load again with skip_existing=True — should skip
        records = loader.load_symbol('AAPL', '2024-01-01', '2024-01-31', skip_existing=True)
        assert records == 0

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_force_reload(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_yf_dataframe()
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)

        loader.load_symbol('AAPL', '2024-01-01', '2024-01-31')
        records = loader.load_symbol('AAPL', '2024-01-01', '2024-01-31', skip_existing=False)
        assert records == 5

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_empty_yfinance_data(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        records = loader.load_symbol('FAKE', '2024-01-01', '2024-01-31')
        assert records == 0

    def test_invalid_symbol_empty_string(self, test_db):
        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        with pytest.raises(ValidationError, match="non-empty string"):
            loader.load_symbol('', '2024-01-01', '2024-01-31')

    def test_invalid_symbol_none(self, test_db):
        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        with pytest.raises(ValidationError, match="non-empty string"):
            loader.load_symbol(None, '2024-01-01', '2024-01-31')

    def test_invalid_start_date_empty(self, test_db):
        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        with pytest.raises(ValidationError):
            loader.load_symbol('AAPL', '', '2024-01-31')

    def test_invalid_end_date_empty(self, test_db):
        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        with pytest.raises(ValidationError):
            loader.load_symbol('AAPL', '2024-01-01', '')

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_request_count_increments(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_yf_dataframe()
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        assert loader.request_count == 0
        loader.load_symbol('AAPL', '2024-01-01', '2024-01-31')
        assert loader.request_count == 1

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_load_with_metadata(self, mock_yf, test_db):
        """Test loading a symbol with custom metadata fields."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_yf_dataframe()
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        records = loader.load_symbol(
            symbol='AAPL',
            start_date='2024-01-01',
            end_date='2024-01-31',
            description='Apple Inc.',
            country='US',
            currency='USD',
            sector='Technology',
        )
        assert records == 5

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_without_adj_close_column(self, mock_yf, test_db):
        """Test loading when yfinance data has no Adj Close column — falls back to Close."""
        dates = pd.date_range('2024-01-02', periods=3, freq='B')
        df_no_adj = pd.DataFrame({
            'Open': [150.0, 151.0, 152.0],
            'High': [155.0, 156.0, 157.0],
            'Low': [149.0, 150.0, 151.0],
            'Close': [153.0, 154.0, 155.0],
            'Volume': [1000000, 1100000, 1200000],
        }, index=dates)
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df_no_adj
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        records = loader.load_symbol('AAPL', '2024-01-01', '2024-01-31')
        assert records == 3


class TestLoadSymbols:

    def _make_mock_df(self, periods=3):
        dates = pd.date_range('2024-01-02', periods=periods, freq='B')
        return pd.DataFrame({
            'Open': [150.0 + i for i in range(periods)],
            'High': [155.0 + i for i in range(periods)],
            'Low': [149.0 + i for i in range(periods)],
            'Close': [153.0 + i for i in range(periods)],
            'Adj Close': [152.0 + i for i in range(periods)],
            'Volume': [1000000 + i * 100000 for i in range(periods)],
        }, index=dates)

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_load_multiple(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_df(3)
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        total = loader.load_symbols(
            ['AAPL', 'MSFT'],
            start_date='2024-01-01',
            end_date='2024-01-31',
        )
        assert total == 6  # 3 records x 2 symbols

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_max_symbols_limit(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_df(1)
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        total = loader.load_symbols(
            ['AAPL', 'MSFT', 'GOOGL'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            max_symbols=2,
        )
        # Should only load 2 of 3 symbols
        assert mock_yf.Ticker.call_count == 2

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_load_symbols_returns_total(self, mock_yf, test_db):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_df(5)
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        total = loader.load_symbols(
            ['AAPL', 'MSFT', 'GOOGL'],
            start_date='2024-01-01',
            end_date='2024-01-31',
            skip_existing=False,
        )
        assert total == 15  # 5 records x 3 symbols

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_load_symbols_skip_existing(self, mock_yf, test_db):
        """After initial load, skip_existing=True should not reload."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_df(3)
        mock_yf.Ticker.return_value = mock_ticker

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)

        # First load
        loader.load_symbols(['AAPL', 'MSFT'], '2024-01-01', '2024-01-31')

        # Second load with skip_existing=True
        call_count_before = mock_yf.Ticker.call_count
        total = loader.load_symbols(
            ['AAPL', 'MSFT'],
            '2024-01-01',
            '2024-01-31',
            skip_existing=True,
        )
        # No new yfinance calls
        assert mock_yf.Ticker.call_count == call_count_before
        assert total == 0

    @patch('finbase.data.loaders.equity_loader.yf')
    def test_empty_symbols_list(self, mock_yf, test_db):
        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        total = loader.load_symbols([], '2024-01-01', '2024-01-31')
        assert total == 0
        mock_yf.Ticker.assert_not_called()
