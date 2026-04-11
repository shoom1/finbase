"""
DataClient - Client API for accessing FinBase database.

Provides simple, intuitive interface for querying financial data.
"""

import pandas as pd
from typing import List, Optional, Union, Dict, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

from ..data.database import TimeSeriesDB, DatabaseError
from ..data.database.index_db import IndexDB
from ..config import get_settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DataClient:
    """
    Client for querying financial data from FinBase database.

    Provides high-level API for data discovery and retrieval without
    requiring direct database knowledge.

    Example:
        ```python
        from finbase import DataClient

        client = DataClient()

        # Get data for single symbol
        df = client.get_data('AAPL', start='2020-01-01')

        # Get data for multiple symbols
        df = client.get_data(['AAPL', 'MSFT'], columns=['close', 'volume'])

        # List available symbols
        symbols = client.list_symbols(asset_class='equity')
        ```

    Data Format:
        Returns long-format DataFrame with columns:
        - date: Trading date
        - symbol: Ticker symbol
        - data_source: Source of data (e.g., 'yfinance')
        - metric: Data column (e.g., 'close', 'volume')
        - value: Numeric value

        Missing data is not filled - rows simply don't exist.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize DataClient.

        Args:
            db_path: Optional database path. If None, uses path from settings
                     (which reads from ~/.finbaserc)
        """
        self.db_path = db_path or get_settings().database.path
        self._db: Optional[TimeSeriesDB] = None
        logger.debug(f"DataClient initialized with database: {self.db_path}")

    def __enter__(self):
        """Open a persistent database connection."""
        self._db = TimeSeriesDB(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the persistent database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None
        return False

    @contextmanager
    def _get_db(self):
        """
        Get database connection as a context manager.

        If DataClient is used as a context manager, reuses the persistent
        connection (does not close it on exit).
        Otherwise, creates a temporary connection and closes it on exit.
        """
        if self._db is not None:
            yield self._db
        else:
            db = TimeSeriesDB(self.db_path)
            try:
                yield db
            finally:
                db.close()

    def get_data(
        self,
        symbols: Union[str, List[str]],
        start: Optional[str] = None,
        end: Optional[str] = None,
        columns: Optional[List[str]] = None,
        data_source: str = 'yfinance',
        format: str = 'long'
    ) -> pd.DataFrame:
        """
        Get time series data for one or more symbols.

        Args:
            symbols: Single symbol or list of symbols
            start: Start date (YYYY-MM-DD). If None, returns all available data
            end: End date (YYYY-MM-DD). If None, returns up to latest data
            columns: List of columns to return. If None, returns all OHLCV columns
                     Valid: ['open', 'high', 'low', 'close', 'adj_close', 'volume']
            data_source: Data source filter (default: 'yfinance')
            format: Return format - 'long' or 'wide'
                    'long': columns = [date, symbol, data_source, metric, value]
                    'wide': multi-index with (date, symbol) and columns for each metric

        Returns:
            DataFrame in long format:
                - date: Trading date
                - symbol: Ticker symbol
                - data_source: Data source
                - metric: Column name (close, volume, etc.)
                - value: Numeric value

            Or DataFrame in wide format (if format='wide'):
                - Index: (date, symbol)
                - Columns: Requested metrics

        Examples:
            >>> client = DataClient()
            >>>
            >>> # Single symbol, all columns
            >>> df = client.get_data('AAPL')
            >>>
            >>> # Multiple symbols, specific date range
            >>> df = client.get_data(['AAPL', 'MSFT'],
            ...                       start='2020-01-01',
            ...                       end='2023-12-31')
            >>>
            >>> # Specific columns only
            >>> df = client.get_data('AAPL', columns=['close', 'volume'])
        """
        # Normalize symbols to list
        if isinstance(symbols, str):
            symbols = [symbols]

        # Default columns if not specified
        if columns is None:
            columns = ['open', 'high', 'low', 'close', 'adj_close', 'volume']

        # Validate columns
        valid_columns = {'open', 'high', 'low', 'close', 'adj_close', 'volume'}
        invalid = set(columns) - valid_columns
        if invalid:
            raise ValueError(f"Invalid columns: {invalid}. Valid: {valid_columns}")

        # Early return for empty symbols
        if not symbols:
            return pd.DataFrame(columns=['date', 'symbol', 'data_source', 'metric', 'value'])

        # Query all symbols at once per column (avoids N+1 query pattern)
        all_data = []

        with self._get_db() as db:
            for column in columns:
                try:
                    df = db.query(
                        symbols=symbols,
                        start_date=start,
                        end_date=end,
                        column=column,
                        data_source=data_source
                    )
                except DatabaseError:
                    # No data found for these symbols/date range
                    continue

                if not df.empty:
                    df_long = df.reset_index()
                    df_long = df_long.melt(
                        id_vars=['date'],
                        var_name='symbol',
                        value_name='value'
                    )
                    df_long['data_source'] = data_source
                    df_long['metric'] = column
                    all_data.append(df_long)

        # Combine all data
        if not all_data:
            # Return empty DataFrame with correct schema
            return pd.DataFrame(columns=['date', 'symbol', 'data_source', 'metric', 'value'])

        result = pd.concat(all_data, ignore_index=True)

        # Reorder columns
        result = result[['date', 'symbol', 'data_source', 'metric', 'value']]

        # Sort by date and symbol
        result = result.sort_values(['date', 'symbol', 'metric']).reset_index(drop=True)

        # Convert to wide format if requested
        if format == 'wide':
            result = result.pivot_table(
                index=['date', 'symbol'],
                columns='metric',
                values='value',
                aggfunc='first'
            )
            result.columns.name = None

        return result

    def get_closes(
        self,
        symbols: Union[str, List[str]],
        start: Optional[str] = None,
        end: Optional[str] = None,
        data_source: str = 'yfinance'
    ) -> pd.DataFrame:
        """
        Get closing prices for symbols (convenience method).

        Returns wide format with date index and symbol columns.

        Args:
            symbols: Single symbol or list of symbols
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            data_source: Data source filter

        Returns:
            DataFrame with date index and columns for each symbol
        """
        if isinstance(symbols, str):
            symbols = [symbols]

        with self._get_db() as db:
            df = db.query(
                symbols=symbols,
                start_date=start,
                end_date=end,
                column='close',
                data_source=data_source
            )

        return df

    def list_symbols(
        self,
        asset_class: Optional[str] = None,
        sector: Optional[str] = None,
        country: Optional[str] = None
    ) -> List[str]:
        """
        List available symbols with optional filters.

        Args:
            asset_class: Filter by asset class (e.g., 'equity', 'fx')
            sector: Filter by sector (e.g., 'Technology')
            country: Filter by country (e.g., 'US')

        Returns:
            List of symbol strings

        Example:
            >>> client.list_symbols(asset_class='equity', sector='Technology')
            ['AAPL', 'MSFT', 'GOOGL', ...]
        """
        with self._get_db() as db:
            df = db.list_risk_factors(
                asset_class=asset_class,
                country=country,
                sector=sector
            )

        return df['symbol'].tolist() if not df.empty else []

    def get_symbol_info(
        self,
        symbol: str,
        data_source: str = 'yfinance'
    ) -> Optional[Dict]:
        """
        Get metadata for a symbol.

        Args:
            symbol: Ticker symbol
            data_source: Data source filter

        Returns:
            Dictionary with metadata:
                - symbol, asset_class, asset_subclass
                - description, country, currency, sector
                - data_source, frequency
                - start_date, end_date, last_updated

            Returns None if symbol doesn't exist.

        Example:
            >>> info = client.get_symbol_info('AAPL')
            >>> print(f"{info['symbol']}: {info['start_date']} to {info['end_date']}")
        """
        with self._get_db() as db:
            return db.get_risk_factor_info(symbol, data_source)

    def search_symbols(
        self,
        pattern: Optional[str] = None,
        asset_class: Optional[str] = None,
        sector: Optional[str] = None,
        country: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Search for symbols matching criteria.

        Args:
            pattern: Symbol pattern with wildcards (* or %)
                     Example: 'AA*' matches AAPL, AAPL, etc.
            asset_class: Filter by asset class
            sector: Filter by sector
            country: Filter by country

        Returns:
            DataFrame with matching symbols and metadata

        Example:
            >>> # Find all tech stocks starting with 'A'
            >>> df = client.search_symbols(pattern='A*', sector='Technology')
        """
        with self._get_db() as db:
            df = db.list_risk_factors(
                asset_class=asset_class,
                country=country,
                sector=sector
            )

        # Apply pattern filter if specified
        if pattern and not df.empty:
            # Convert SQL wildcard to regex
            regex_pattern = pattern.replace('*', '.*').replace('%', '.*')
            df = df[df['symbol'].str.match(f'^{regex_pattern}$', case=False)]

        return df

    def has_symbol(
        self,
        symbol: str,
        data_source: str = 'yfinance'
    ) -> bool:
        """
        Check if symbol exists in database.

        Args:
            symbol: Ticker symbol
            data_source: Data source filter

        Returns:
            True if symbol exists, False otherwise

        Example:
            >>> if client.has_symbol('AAPL'):
            ...     df = client.get_data('AAPL')
        """
        info = self.get_symbol_info(symbol, data_source)
        return info is not None

    def get_date_range(
        self,
        symbol: str,
        data_source: str = 'yfinance'
    ) -> Optional[Tuple[str, str]]:
        """
        Get available date range for a symbol.

        Args:
            symbol: Ticker symbol
            data_source: Data source filter

        Returns:
            Tuple of (start_date, end_date) as strings, or None if not found

        Example:
            >>> start, end = client.get_date_range('AAPL')
            >>> print(f"Data available from {start} to {end}")
        """
        info = self.get_symbol_info(symbol, data_source)
        if info and info.get('start_date') and info.get('end_date'):
            return (str(info['start_date']), str(info['end_date']))
        return None

    def get_latest(
        self,
        symbols: Union[str, List[str]],
        days: int = 30,
        columns: Optional[List[str]] = None,
        data_source: str = 'yfinance'
    ) -> pd.DataFrame:
        """
        Get latest N days of data for symbols.

        Args:
            symbols: Single symbol or list of symbols
            days: Number of days to retrieve (default: 30)
            columns: Columns to return (default: all)
            data_source: Data source filter

        Returns:
            DataFrame in long format

        Example:
            >>> # Get last month of data
            >>> df = client.get_latest('AAPL', days=30)
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        return self.get_data(
            symbols=symbols,
            start=start_date,
            end=end_date,
            columns=columns,
            data_source=data_source
        )

    def get_all(
        self,
        symbols: Union[str, List[str]],
        columns: Optional[List[str]] = None,
        data_source: str = 'yfinance'
    ) -> pd.DataFrame:
        """
        Get all available data for symbols.

        Args:
            symbols: Single symbol or list of symbols
            columns: Columns to return (default: all)
            data_source: Data source filter

        Returns:
            DataFrame in long format

        Example:
            >>> # Get all historical data
            >>> df = client.get_all('AAPL')
        """
        return self.get_data(
            symbols=symbols,
            start=None,
            end=None,
            columns=columns,
            data_source=data_source
        )

    def get_stats(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dictionary with:
                - total_symbols: Number of symbols
                - asset_classes: List of asset classes
                - data_sources: List of data sources
                - date_range: (earliest_date, latest_date)
                - by_asset_class: Count by asset class

        Example:
            >>> stats = client.get_stats()
            >>> print(f"Database has {stats['total_symbols']} symbols")
        """
        with self._get_db() as db:
            df = db.list_risk_factors()

        if df.empty:
            return {
                'total_symbols': 0,
                'asset_classes': [],
                'data_sources': [],
                'date_range': (None, None),
                'by_asset_class': {}
            }

        return {
            'total_symbols': len(df),
            'asset_classes': df['asset_class'].unique().tolist(),
            'data_sources': df['data_source'].unique().tolist(),
            'date_range': (
                df['start_date'].min() if 'start_date' in df.columns else None,
                df['end_date'].max() if 'end_date' in df.columns else None
            ),
            'by_asset_class': df['asset_class'].value_counts().to_dict()
        }

    def get_by_asset_class(
        self,
        asset_class: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get data for all symbols in an asset class.

        Args:
            asset_class: Asset class (e.g., 'equity', 'fx')
            start: Start date
            end: End date
            columns: Columns to return

        Returns:
            DataFrame in long format

        Example:
            >>> # Get all equity data
            >>> df = client.get_by_asset_class('equity', start='2020-01-01')
        """
        symbols = self.list_symbols(asset_class=asset_class)
        if not symbols:
            return pd.DataFrame(columns=['date', 'symbol', 'data_source', 'metric', 'value'])

        return self.get_data(symbols, start=start, end=end, columns=columns)

    def get_by_sector(
        self,
        sector: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Get data for all symbols in a sector.

        Args:
            sector: Sector name (e.g., 'Technology')
            start: Start date
            end: End date
            columns: Columns to return

        Returns:
            DataFrame in long format

        Example:
            >>> # Get all technology stocks
            >>> df = client.get_by_sector('Technology', start='2020-01-01')
        """
        symbols = self.list_symbols(sector=sector)
        if not symbols:
            return pd.DataFrame(columns=['date', 'symbol', 'data_source', 'metric', 'value'])

        return self.get_data(symbols, start=start, end=end, columns=columns)

    # ========================================================================
    # INDEX CONSTITUENT METHODS
    # ========================================================================

    def get_index_constituents(
        self,
        index_code: str,
        as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get index constituents, current or historical.

        Args:
            index_code: Index code (e.g., 'SP500', 'DOW30')
            as_of_date: Date to get constituents as of (YYYY-MM-DD)
                       If None, returns current constituents

        Returns:
            DataFrame with constituents

        Example:
            >>> # Get current S&P 500 constituents
            >>> sp500 = client.get_index_constituents('SP500')

            >>> # Get historical composition
            >>> sp500_2020 = client.get_index_constituents('SP500', as_of_date='2020-01-01')
        """
        with self._get_db() as db:
            index_db = IndexDB(db)

            if as_of_date is None:
                return index_db.get_current_constituents(index_code)
            else:
                return index_db.get_historical_constituents(index_code, as_of_date)

    def list_indices(self) -> pd.DataFrame:
        """
        List all registered indices.

        Returns:
            DataFrame with index information

        Example:
            >>> indices = client.list_indices()
            >>> print(indices[['index_code', 'index_name', 'last_updated']])
        """
        with self._get_db() as db:
            index_db = IndexDB(db)
            return index_db.list_indices()

    def is_index_member(
        self,
        symbol: str,
        index_code: str,
        date: Optional[str] = None
    ) -> bool:
        """
        Check if symbol was in index on a specific date.

        Args:
            symbol: Stock symbol
            index_code: Index code (e.g., 'SP500')
            date: Date to check (YYYY-MM-DD). If None, checks current membership

        Returns:
            True if symbol was member on that date

        Example:
            >>> # Was Tesla in S&P 500 in Dec 2020?
            >>> client.is_index_member('TSLA', 'SP500', date='2020-12-01')  # False
            >>> client.is_index_member('TSLA', 'SP500', date='2021-01-01')  # True
        """
        with self._get_db() as db:
            index_db = IndexDB(db)
            return index_db.is_index_member(symbol, index_code, check_date=date)

    def get_index_changes(
        self,
        index_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get index composition changes in a date range.

        Args:
            index_code: Index code
            start_date: Start date (optional)
            end_date: End date (optional)

        Returns:
            DataFrame with changes (additions and removals)

        Example:
            >>> # Get all changes in 2024
            >>> changes = client.get_index_changes('SP500', start_date='2024-01-01', end_date='2024-12-31')
            >>> additions = changes[changes['change_type'] == 'added']
            >>> removals = changes[changes['change_type'] == 'removed']
        """
        with self._get_db() as db:
            index_db = IndexDB(db)
            return index_db.get_index_changes(index_code, start_date, end_date)
