"""
Data service for dashboard - aggregates database statistics.

This module provides cached data aggregation for the dashboard to improve performance.
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from ..data.database import TimeSeriesDB
from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DashboardDataService:
    """Service for aggregating dashboard data with caching."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize dashboard data service.

        Args:
            db_path: Path to database (uses config default if None)
        """
        settings = get_settings()
        self.db_path = db_path or settings.database.path
        self._cache = {}
        self._cache_timestamp = {}
        self.cache_ttl = 300  # 5 minutes cache TTL

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_timestamp:
            return False

        age = datetime.now() - self._cache_timestamp[key]
        return age.total_seconds() < self.cache_ttl

    def _get_cached(self, key: str):
        """Get cached data if valid."""
        if self._is_cache_valid(key):
            logger.debug(f"Cache hit for {key}")
            return self._cache.get(key)
        return None

    def _set_cache(self, key: str, value):
        """Set cache with timestamp."""
        self._cache[key] = value
        self._cache_timestamp[key] = datetime.now()
        logger.debug(f"Cache set for {key}")

    def clear_cache(self):
        """Clear all cached data."""
        self._cache = {}
        self._cache_timestamp = {}
        logger.info("Cache cleared")

    def get_overview_stats(self) -> Dict:
        """
        Get overview statistics for the dashboard.

        Returns:
            Dictionary with overview metrics
        """
        cache_key = "overview_stats"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        logger.info("Computing overview statistics")

        with TimeSeriesDB(self.db_path) as db:
            # Get all risk factors
            risk_factors = db.list_risk_factors()

            if risk_factors.empty:
                stats = {
                    'total_symbols': 0,
                    'total_data_points': 0,
                    'asset_classes': 0,
                    'date_range': None,
                    'database_size_mb': 0,
                    'last_updated': None
                }
                self._set_cache(cache_key, stats)
                return stats

            # Get database size
            db_path_obj = Path(self.db_path)
            db_size_mb = db_path_obj.stat().st_size / (1024 * 1024) if db_path_obj.exists() else 0

            # Count total data points
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM timeseries_data")
            total_data_points = cursor.fetchone()[0]

            # Get date range
            cursor.execute("SELECT MIN(date), MAX(date) FROM timeseries_data")
            min_date, max_date = cursor.fetchone()

            # Get last updated
            cursor.execute("SELECT MAX(last_updated) FROM risk_factors")
            last_updated = cursor.fetchone()[0]

            stats = {
                'total_symbols': len(risk_factors),
                'total_data_points': total_data_points,
                'asset_classes': risk_factors['asset_class'].nunique(),
                'sectors': risk_factors['sector'].nunique() if 'sector' in risk_factors.columns else 0,
                'countries': risk_factors['country'].nunique() if 'country' in risk_factors.columns else 0,
                'date_range': f"{min_date} to {max_date}" if min_date and max_date else None,
                'earliest_date': min_date,
                'latest_date': max_date,
                'database_size_mb': round(db_size_mb, 2),
                'last_updated': last_updated
            }

        self._set_cache(cache_key, stats)
        return stats

    def get_data_coverage(self) -> pd.DataFrame:
        """
        Get data coverage information for all symbols.

        Returns:
            DataFrame with columns: symbol, start_date, end_date, data_points, coverage_pct
        """
        cache_key = "data_coverage"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        logger.info("Computing data coverage")

        with TimeSeriesDB(self.db_path) as db:
            cursor = db.conn.cursor()

            # Get coverage data for each symbol
            query = """
                SELECT
                    rf.symbol,
                    rf.asset_class,
                    rf.sector,
                    rf.start_date,
                    rf.end_date,
                    COUNT(td.ts_id) as data_points,
                    MIN(td.date) as actual_start,
                    MAX(td.date) as actual_end
                FROM risk_factors rf
                LEFT JOIN timeseries_data td ON rf.risk_factor_id = td.risk_factor_id
                WHERE rf.is_active = 1
                GROUP BY rf.risk_factor_id, rf.symbol, rf.asset_class, rf.sector, rf.start_date, rf.end_date
                ORDER BY rf.asset_class, rf.symbol
            """

            df = pd.read_sql_query(query, db.conn)

            if not df.empty:
                # Calculate coverage percentage
                df['actual_start'] = pd.to_datetime(df['actual_start'])
                df['actual_end'] = pd.to_datetime(df['actual_end'])

                # Calculate expected business days
                df['expected_days'] = df.apply(
                    lambda row: len(pd.date_range(row['actual_start'], row['actual_end'], freq='B'))
                    if pd.notna(row['actual_start']) and pd.notna(row['actual_end']) else 0,
                    axis=1
                )

                df['coverage_pct'] = (df['data_points'] / df['expected_days'] * 100).round(2)
                df['coverage_pct'] = df['coverage_pct'].fillna(0)

        self._set_cache(cache_key, df)
        return df

    def get_asset_distribution(self) -> Dict[str, pd.DataFrame]:
        """
        Get distribution of assets by various categories.

        Returns:
            Dictionary with DataFrames for different distributions
        """
        cache_key = "asset_distribution"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        logger.info("Computing asset distribution")

        with TimeSeriesDB(self.db_path) as db:
            risk_factors = db.list_risk_factors()

            if risk_factors.empty:
                return {}

            distributions = {}

            # Asset class distribution
            asset_class_dist = risk_factors['asset_class'].value_counts().reset_index()
            asset_class_dist.columns = ['asset_class', 'count']
            distributions['asset_class'] = asset_class_dist

            # Sector distribution (for equities)
            if 'sector' in risk_factors.columns:
                sector_dist = risk_factors[risk_factors['sector'].notna()]['sector'].value_counts().reset_index()
                sector_dist.columns = ['sector', 'count']
                distributions['sector'] = sector_dist

            # Country distribution
            if 'country' in risk_factors.columns:
                country_dist = risk_factors[risk_factors['country'].notna()]['country'].value_counts().reset_index()
                country_dist.columns = ['country', 'count']
                distributions['country'] = country_dist

            # Currency distribution
            if 'currency' in risk_factors.columns:
                currency_dist = risk_factors[risk_factors['currency'].notna()]['currency'].value_counts().reset_index()
                currency_dist.columns = ['currency', 'count']
                distributions['currency'] = currency_dist

        self._set_cache(cache_key, distributions)
        return distributions

    def get_data_freshness(self) -> pd.DataFrame:
        """
        Get data freshness information for all symbols.

        Returns:
            DataFrame with freshness indicators
        """
        cache_key = "data_freshness"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        logger.info("Computing data freshness")

        with TimeSeriesDB(self.db_path) as db:
            risk_factors = db.list_risk_factors()

            if risk_factors.empty:
                return pd.DataFrame()

            # Calculate age of data
            now = datetime.now()

            risk_factors['last_updated'] = pd.to_datetime(risk_factors['last_updated'])
            risk_factors['end_date'] = pd.to_datetime(risk_factors['end_date'])

            # Days since last update
            risk_factors['days_since_update'] = (now - risk_factors['last_updated']).dt.days

            # Days since end of data
            risk_factors['days_stale'] = (now - risk_factors['end_date']).dt.days

            # Freshness status
            def get_freshness_status(days):
                if pd.isna(days):
                    return 'Unknown'
                elif days <= 1:
                    return 'Fresh'
                elif days <= 7:
                    return 'Current'
                elif days <= 30:
                    return 'Stale'
                else:
                    return 'Old'

            risk_factors['freshness_status'] = risk_factors['days_stale'].apply(get_freshness_status)

            # Select relevant columns
            freshness_df = risk_factors[[
                'symbol', 'asset_class', 'sector', 'end_date', 'last_updated',
                'days_since_update', 'days_stale', 'freshness_status'
            ]].copy()

            # Sort by staleness (most stale first)
            freshness_df = freshness_df.sort_values('days_stale', ascending=False)

        self._set_cache(cache_key, freshness_df)
        return freshness_df

    def get_data_quality_summary(self) -> Dict:
        """
        Get summary of data quality across all symbols.

        Returns:
            Dictionary with quality metrics
        """
        cache_key = "data_quality"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        logger.info("Computing data quality summary")

        coverage_df = self.get_data_coverage()

        if coverage_df.empty:
            return {
                'avg_coverage': 0,
                'symbols_with_full_coverage': 0,
                'symbols_with_gaps': 0
            }

        quality = {
            'avg_coverage': coverage_df['coverage_pct'].mean().round(2),
            'median_coverage': coverage_df['coverage_pct'].median().round(2),
            'symbols_with_full_coverage': len(coverage_df[coverage_df['coverage_pct'] >= 99]),
            'symbols_with_gaps': len(coverage_df[coverage_df['coverage_pct'] < 95]),
            'min_coverage': coverage_df['coverage_pct'].min().round(2),
            'max_coverage': coverage_df['coverage_pct'].max().round(2)
        }

        self._set_cache(cache_key, quality)
        return quality
