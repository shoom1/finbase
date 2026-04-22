"""Pytest configuration and shared fixtures."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from finbase.data.database import TimeSeriesDB
from finbase.data.database.index_db import IndexDB


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_timeseries.db"
    yield str(db_path)
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_db(temp_db_path):
    """Create an in-memory test database with schema initialized."""
    with TimeSeriesDB(temp_db_path) as db:
        db.initialize_schema()
        yield db


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', end='2024-01-31', freq='B')
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

    return data


@pytest.fixture
def sample_ohlcv_data_with_index(sample_ohlcv_data):
    """Sample OHLCV data with date as index instead of column."""
    df = sample_ohlcv_data.copy()
    df = df.set_index('date')
    return df


@pytest.fixture
def sample_risk_factor_data():
    """Sample risk factor metadata."""
    return {
        'symbol': 'TEST',
        'asset_class': 'equity',
        'data_source': 'test_source',
        'frequency': 'daily',
        'asset_subclass': 'stock',
        'description': 'Test Stock',
        'currency': 'USD',
        'country': 'US',
        'sector': 'Technology',
        'metadata': {'test_key': 'test_value'}
    }


@pytest.fixture
def populated_db(test_db, sample_risk_factor_data, sample_ohlcv_data):
    """Database with sample risk factor and timeseries data."""
    # Add risk factor
    rf_id = test_db.add_risk_factor(**sample_risk_factor_data)

    # Add timeseries data
    test_db.add_timeseries_data(
        risk_factor_id=rf_id,
        data=sample_ohlcv_data
    )

    return test_db


@pytest.fixture
def multiple_symbols_db(test_db):
    """Database with multiple symbols for testing queries."""
    symbols_data = [
        {
            'symbol': 'AAPL',
            'asset_class': 'equity',
            'data_source': 'yfinance',
            'description': 'Apple Inc.',
            'sector': 'Technology'
        },
        {
            'symbol': 'MSFT',
            'asset_class': 'equity',
            'data_source': 'yfinance',
            'description': 'Microsoft Corp.',
            'sector': 'Technology'
        },
        {
            'symbol': 'JPM',
            'asset_class': 'equity',
            'data_source': 'yfinance',
            'description': 'JPMorgan Chase',
            'sector': 'Financials'
        }
    ]

    dates = pd.date_range(start='2024-01-01', end='2024-01-31', freq='B')

    for sym_data in symbols_data:
        # Add risk factor
        rf_id = test_db.add_risk_factor(**sym_data)

        # Generate data for this symbol
        n = len(dates)
        data = pd.DataFrame({
            'date': dates,
            'close': np.random.uniform(100, 200, n),
            'adj_close': np.random.uniform(100, 200, n),
            'open': np.random.uniform(100, 200, n),
            'high': np.random.uniform(200, 250, n),
            'low': np.random.uniform(90, 100, n),
            'volume': np.random.randint(1000000, 10000000, n)
        })

        test_db.add_timeseries_data(rf_id, data)

    return test_db


@pytest.fixture
def index_db(test_db):
    """IndexDB instance backed by a test database with schema initialized."""
    return IndexDB(test_db)


@pytest.fixture
def sample_constituents_df():
    """Sample constituents DataFrame matching WikipediaIndexParser output."""
    return pd.DataFrame({
        'symbol': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
        'company_name': ['Apple Inc.', 'Microsoft Corp.', 'Alphabet Inc.', 'Amazon.com Inc.', 'Meta Platforms Inc.'],
        'sector': ['Technology', 'Technology', 'Communication Services', 'Consumer Discretionary', 'Communication Services'],
        'sub_industry': ['Tech Hardware', 'Software', 'Interactive Media', 'Broadline Retail', 'Interactive Media'],
        'source': ['wikipedia'] * 5,
    })


@pytest.fixture
def populated_index_db(index_db, sample_constituents_df):
    """IndexDB with a registered SP500 index and 5 constituents."""
    index_db.register_index(
        index_code='SP500',
        index_name='S&P 500',
        description='Standard and Poors 500',
        country='US',
        data_source='wikipedia',
    )
    index_db.update_constituents(
        index_code='SP500',
        constituents_df=sample_constituents_df,
    )
    return index_db
