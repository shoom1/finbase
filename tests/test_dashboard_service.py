"""Tests for DashboardDataService - dashboard data aggregation."""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

from finbase.dashboard.data_service import DashboardDataService


@pytest.fixture
def dashboard_service(temp_db_path, multiple_symbols_db):
    """DashboardDataService backed by a database with 3 symbols."""
    return DashboardDataService(db_path=temp_db_path)


class TestOverviewStats:

    def test_returns_expected_keys(self, dashboard_service):
        stats = dashboard_service.get_overview_stats()
        assert 'total_symbols' in stats
        assert 'total_data_points' in stats
        assert 'asset_classes' in stats
        assert 'database_size_mb' in stats

    def test_total_symbols_matches(self, dashboard_service):
        stats = dashboard_service.get_overview_stats()
        assert stats['total_symbols'] == 3

    def test_data_points_nonzero(self, dashboard_service):
        stats = dashboard_service.get_overview_stats()
        assert stats['total_data_points'] > 0

    def test_empty_database(self, temp_db_path, test_db):
        service = DashboardDataService(db_path=temp_db_path)
        stats = service.get_overview_stats()
        assert stats['total_symbols'] == 0
        assert stats['total_data_points'] == 0


class TestDataCoverage:

    def test_returns_dataframe(self, dashboard_service):
        df = dashboard_service.get_data_coverage()
        assert isinstance(df, pd.DataFrame)
        assert 'symbol' in df.columns
        assert 'data_points' in df.columns

    def test_coverage_has_all_symbols(self, dashboard_service):
        df = dashboard_service.get_data_coverage()
        assert set(df['symbol']) == {'AAPL', 'MSFT', 'JPM'}


class TestAssetDistribution:

    def test_returns_dict(self, dashboard_service):
        dist = dashboard_service.get_asset_distribution()
        assert isinstance(dist, dict)
        assert 'asset_class' in dist

    def test_sector_distribution(self, dashboard_service):
        dist = dashboard_service.get_asset_distribution()
        if 'sector' in dist:
            sector_df = dist['sector']
            assert 'Technology' in sector_df['sector'].values


class TestDataFreshness:

    def test_returns_dataframe(self, dashboard_service):
        df = dashboard_service.get_data_freshness()
        assert isinstance(df, pd.DataFrame)
        assert 'freshness_status' in df.columns

    def test_all_symbols_present(self, dashboard_service):
        df = dashboard_service.get_data_freshness()
        assert len(df) == 3


class TestCache:

    def test_cache_hit(self, dashboard_service):
        # First call populates cache
        stats1 = dashboard_service.get_overview_stats()
        # Second call should hit cache
        stats2 = dashboard_service.get_overview_stats()
        assert stats1 == stats2

    def test_clear_cache(self, dashboard_service):
        dashboard_service.get_overview_stats()
        dashboard_service.clear_cache()
        assert dashboard_service._cache == {}
