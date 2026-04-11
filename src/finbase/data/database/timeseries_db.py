"""Main time series database interface."""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Union
from datetime import datetime
import json
import time

from .schema import get_all_schemas
from ...utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Valid asset classes
VALID_ASSET_CLASSES = {'equity', 'fx', 'rates', 'commodity', 'credit', 'crypto'}

# Valid data frequencies
VALID_FREQUENCIES = {'tick', 'minute', 'hourly', 'daily', 'weekly', 'monthly'}

# Valid columns for querying
VALID_QUERY_COLUMNS = {'open', 'high', 'low', 'close', 'adj_close', 'volume'}


class DatabaseError(Exception):
    """Base exception for database operations."""
    pass


class ValidationError(Exception):
    """Exception for data validation errors."""
    pass


class TimeSeriesDB:
    """SQLite-based time series database for financial risk factors."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. If None, uses path from
                     Settings (which reads from ~/.finbaserc or defaults to
                     ~/.finbase/timeseries.db)

        Raises:
            DatabaseError: If connection cannot be established
        """
        if db_path is None:
            # Import here to avoid circular imports
            from ...config import get_settings
            db_path = get_settings().database.path

        self.db_path = Path(db_path).expanduser()
        self.conn = None
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connect()
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database at {self.db_path}: {e}")

    def _connect(self, max_retries: int = 3):
        """
        Establish database connection with retry logic.

        Args:
            max_retries: Maximum number of connection attempts

        Raises:
            DatabaseError: If connection fails after all retries
        """
        for attempt in range(max_retries):
            try:
                self.conn = sqlite3.connect(
                    str(self.db_path),
                    timeout=30.0,
                    check_same_thread=False
                )
                self.conn.row_factory = sqlite3.Row
                # Enable foreign keys
                self.conn.execute("PRAGMA foreign_keys = ON")
                return
            except sqlite3.Error as e:
                if attempt == max_retries - 1:
                    raise DatabaseError(f"Failed to connect to database after {max_retries} attempts: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()
        return False

    def initialize_schema(self):
        """
        Create all tables and indexes if they don't exist.

        Raises:
            DatabaseError: If schema creation fails
        """
        try:
            cursor = self.conn.cursor()

            for schema_sql in get_all_schemas():
                cursor.execute(schema_sql)

            self.conn.commit()
            logger.info(f"Database schema initialized at {self.db_path}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise DatabaseError(f"Failed to initialize schema: {e}")

    def add_risk_factor(
        self,
        symbol: str,
        asset_class: str,
        data_source: str,
        frequency: str = "daily",
        asset_subclass: Optional[str] = None,
        description: Optional[str] = None,
        currency: Optional[str] = None,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Add a new risk factor to the database.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "EURUSD=X")
            asset_class: Asset class (equity, fx, rates, commodity, credit)
            data_source: Data source (yfinance, fred, bloomberg, etc.)
            frequency: Data frequency (daily, weekly, monthly)
            asset_subclass: Sub-classification (stock, index, spot, future, etc.)
            description: Human-readable description
            currency: Currency denomination (USD, EUR, etc.)
            country: Country code (US, GB, JP, etc.)
            sector: Sector (for equities)
            metadata: Additional metadata as dict (will be JSON serialized)

        Returns:
            risk_factor_id of the inserted/existing record

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        if not symbol or not isinstance(symbol, str):
            raise ValidationError("Symbol must be a non-empty string")

        if not asset_class or not isinstance(asset_class, str):
            raise ValidationError("Asset class must be a non-empty string")

        if asset_class.lower() not in VALID_ASSET_CLASSES:
            raise ValidationError(
                f"Invalid asset class '{asset_class}'. Must be one of: {VALID_ASSET_CLASSES}"
            )

        if not data_source or not isinstance(data_source, str):
            raise ValidationError("Data source must be a non-empty string")

        if frequency.lower() not in VALID_FREQUENCIES:
            raise ValidationError(
                f"Invalid frequency '{frequency}'. Must be one of: {VALID_FREQUENCIES}"
            )

        try:
            cursor = self.conn.cursor()

            # Check if already exists
            cursor.execute(
                "SELECT risk_factor_id FROM risk_factors WHERE symbol = ? AND asset_class = ? AND data_source = ?",
                (symbol, asset_class, data_source)
            )
            existing = cursor.fetchone()

            if existing:
                return existing[0]

            # Insert new risk factor
            metadata_json = json.dumps(metadata) if metadata else None

            cursor.execute(
                """
                INSERT INTO risk_factors (
                    symbol, asset_class, asset_subclass, description, currency,
                    country, sector, data_source, frequency, metadata_json, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol, asset_class, asset_subclass, description, currency,
                    country, sector, data_source, frequency, metadata_json,
                    datetime.now()
                )
            )

            self.conn.commit()
            return cursor.lastrowid

        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            raise DatabaseError(f"Integrity constraint violation: {e}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise DatabaseError(f"Failed to add risk factor: {e}")

    def add_timeseries_data(
        self,
        risk_factor_id: int,
        data: pd.DataFrame,
        date_column: str = 'date',
        close_column: str = 'close',
        adj_close_column: Optional[str] = 'adj_close',
        open_column: Optional[str] = 'open',
        high_column: Optional[str] = 'high',
        low_column: Optional[str] = 'low',
        volume_column: Optional[str] = 'volume'
    ) -> int:
        """
        Add time series data for a risk factor using bulk insertions.

        Args:
            risk_factor_id: ID of the risk factor
            data: DataFrame with time series data
            date_column: Name of date column (or use index if None)
            close_column: Name of close price column
            adj_close_column: Name of adjusted close column
            open_column: Name of open price column
            high_column: Name of high price column
            low_column: Name of low price column
            volume_column: Name of volume column

        Returns:
            Number of records inserted

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        if not isinstance(risk_factor_id, int) or risk_factor_id <= 0:
            raise ValidationError("risk_factor_id must be a positive integer")

        if data is None or data.empty:
            raise ValidationError("Data cannot be None or empty")

        if not isinstance(data, pd.DataFrame):
            raise ValidationError("Data must be a pandas DataFrame")

        try:
            # Prepare data
            df = data.copy()

            # Use index as date if date_column not in columns
            if date_column not in df.columns:
                df = df.reset_index()
                # Check if index is named 'date', 'Date', or just unnamed
                if 'date' in df.columns:
                    date_column = 'date'
                elif 'Date' in df.columns:
                    date_column = 'Date'
                elif 'index' in df.columns:
                    date_column = 'index'
                else:
                    raise ValidationError(f"Cannot find date column '{date_column}' in DataFrame")

            # Convert date to string format
            try:
                df[date_column] = pd.to_datetime(df[date_column]).dt.strftime('%Y-%m-%d')
            except Exception as e:
                raise ValidationError(f"Failed to convert date column to datetime: {e}")

            # Verify close column exists
            if close_column not in df.columns:
                raise ValidationError(f"Close column '{close_column}' not found in DataFrame")

            # Filter rows without close price (vectorized)
            df = df[df[close_column].notna()]

            if df.empty:
                raise ValidationError("No valid records to insert (all close prices are NaN)")

            # Extract column values, converting NaN to None for SQL
            def _col_values(col_param):
                if col_param and col_param in df.columns:
                    return [None if pd.isna(v) else float(v) for v in df[col_param].values]
                return [None] * len(df)

            # Build records using vectorized column access
            records = list(zip(
                [risk_factor_id] * len(df),
                df[date_column].values,
                _col_values(open_column),
                _col_values(high_column),
                _col_values(low_column),
                [float(v) for v in df[close_column].values],
                _col_values(adj_close_column),
                _col_values(volume_column),
            ))

            # Bulk insert using executemany
            cursor = self.conn.cursor()
            cursor.executemany(
                """
                INSERT OR REPLACE INTO timeseries_data (
                    risk_factor_id, date, open, high, low, close, adj_close, volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                records
            )

            # Update risk factor metadata in same transaction
            cursor.execute(
                """
                UPDATE risk_factors
                SET start_date = (SELECT MIN(date) FROM timeseries_data WHERE risk_factor_id = ?),
                    end_date = (SELECT MAX(date) FROM timeseries_data WHERE risk_factor_id = ?),
                    last_updated = ?
                WHERE risk_factor_id = ?
                """,
                (risk_factor_id, risk_factor_id, datetime.now(), risk_factor_id)
            )
            self.conn.commit()

            return len(records)

        except sqlite3.IntegrityError as e:
            self.conn.rollback()
            raise DatabaseError(f"Integrity constraint violation: {e}")
        except sqlite3.Error as e:
            self.conn.rollback()
            raise DatabaseError(f"Failed to add timeseries data: {e}")
        except ValidationError:
            raise
        except Exception as e:
            self.conn.rollback()
            raise DatabaseError(f"Unexpected error adding timeseries data: {e}")

    def query(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        column: str = 'adj_close',
        asset_class: Optional[str] = None,
        data_source: str = 'yfinance'
    ) -> pd.DataFrame:
        """
        Query time series data for multiple symbols.

        Args:
            symbols: List of symbols to query
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            column: Column to return (close, adj_close, open, high, low, volume)
            asset_class: Optional asset class filter
            data_source: Data source filter

        Returns:
            DataFrame with dates as index and symbols as columns

        Raises:
            ValidationError: If input validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        if not symbols or not isinstance(symbols, list):
            raise ValidationError("Symbols must be a non-empty list")

        if not all(isinstance(s, str) for s in symbols):
            raise ValidationError("All symbols must be strings")

        if column not in VALID_QUERY_COLUMNS:
            raise ValidationError(
                f"Invalid column '{column}'. Must be one of: {VALID_QUERY_COLUMNS}"
            )

        # Validate date format
        try:
            pd.to_datetime(start_date)
            pd.to_datetime(end_date)
        except Exception as e:
            raise ValidationError(f"Invalid date format (use YYYY-MM-DD): {e}")

        try:
            cursor = self.conn.cursor()

            # Get risk factor IDs for symbols
            placeholders = ','.join('?' * len(symbols))
            query_params = symbols + [data_source]

            sql = f"""
                SELECT risk_factor_id, symbol
                FROM risk_factors
                WHERE symbol IN ({placeholders})
                AND data_source = ?
            """

            if asset_class:
                sql += " AND asset_class = ?"
                query_params.append(asset_class)

            cursor.execute(sql, query_params)
            risk_factors = cursor.fetchall()

            if not risk_factors:
                raise DatabaseError(f"No risk factors found for symbols: {symbols}")

            # Build mapping
            symbol_to_id = {row[1]: row[0] for row in risk_factors}

            # Query time series data
            result_dfs = []

            for symbol in symbols:
                if symbol not in symbol_to_id:
                    logger.warning(f"Symbol {symbol} not found in database")
                    continue

                rf_id = symbol_to_id[symbol]

                # Safe to use column in f-string after validation
                query_sql = f"""
                    SELECT date, {column}
                    FROM timeseries_data
                    WHERE risk_factor_id = ?
                    AND date >= ?
                    AND date <= ?
                    ORDER BY date
                """

                df = pd.read_sql_query(
                    query_sql,
                    self.conn,
                    params=(rf_id, start_date, end_date),
                    parse_dates=['date'],
                    index_col='date'
                )

                df.columns = [symbol]
                result_dfs.append(df)

            if not result_dfs:
                return pd.DataFrame()

            # Combine all symbols
            result = pd.concat(result_dfs, axis=1)
            return result

        except ValidationError:
            raise
        except DatabaseError:
            raise
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to query timeseries data: {e}")
        except Exception as e:
            raise DatabaseError(f"Unexpected error querying data: {e}")

    def get_risk_factor_info(self, symbol: str, data_source: str = 'yfinance') -> Optional[Dict]:
        """Get metadata for a risk factor."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM risk_factors
            WHERE symbol = ?
            AND data_source = ?
            """,
            (symbol, data_source)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return dict(row)

    def list_risk_factors(
        self,
        asset_class: Optional[str] = None,
        country: Optional[str] = None,
        sector: Optional[str] = None
    ) -> pd.DataFrame:
        """
        List all risk factors with optional filters.

        Args:
            asset_class: Filter by asset class
            country: Filter by country
            sector: Filter by sector

        Returns:
            DataFrame of risk factors
        """
        sql = "SELECT * FROM risk_factors WHERE is_active = 1"
        params = []

        if asset_class:
            sql += " AND asset_class = ?"
            params.append(asset_class)

        if country:
            sql += " AND country = ?"
            params.append(country)

        if sector:
            sql += " AND sector = ?"
            params.append(sector)

        df = pd.read_sql_query(sql, self.conn, params=params)
        return df

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
