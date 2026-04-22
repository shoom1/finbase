"""
Database operations for equity index constituents.

This module manages index metadata and constituent membership with
temporal tracking (slowly changing dimension pattern).
"""

import sqlite3
import pandas as pd
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date

from .timeseries_db import TimeSeriesDB, DatabaseError
from ...utils.logging import get_logger

logger = get_logger(__name__)


def _convert_timestamp(value):
    """
    Convert pandas Timestamp to Python datetime for SQLite compatibility.

    Args:
        value: Value to convert (could be pandas Timestamp, datetime, or None)

    Returns:
        Python datetime object or None
    """
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


class IndexDB:
    """
    Database operations for equity index constituents.

    Manages:
    - Index metadata (indices table)
    - Constituent membership with temporal tracking (index_constituents table)
    - Change detection and history
    """

    def __init__(self, db):
        """
        Initialize IndexDB with a database handle.

        Accepts either a raw ``sqlite3.Connection`` (preferred) or a
        :class:`TimeSeriesDB` instance, from which the connection is
        extracted. Accepting the richer type kept all historical callers
        working while letting new code pass only what this class actually
        needs — a connection. The internal methods always use
        ``self.conn`` so TimeSeriesDB's private attribute is no longer
        load-bearing for index operations.

        Args:
            db: ``sqlite3.Connection`` or ``TimeSeriesDB`` instance.
        """
        if isinstance(db, sqlite3.Connection):
            self.conn = db
        else:
            # Assume a TimeSeriesDB-shaped object exposing ``.conn``.
            # Avoids an isinstance check against TimeSeriesDB to keep
            # IndexDB decoupled from that class at runtime.
            self.conn = db.conn

    def register_index(
        self,
        index_code: str,
        index_name: str,
        description: str,
        country: str,
        data_source: str,
        asset_class: str = 'equity'
    ) -> int:
        """
        Register a new index or update existing one.

        Args:
            index_code: Unique code (e.g., 'SP500', 'DOW30')
            index_name: Full name
            description: Description
            country: Country code
            data_source: Data source (e.g., 'wikipedia')
            asset_class: Asset class (default: 'equity')

        Returns:
            index_id of registered index

        Raises:
            DatabaseError: If registration fails
        """
        try:
            cursor = self.conn.cursor()

            # Check if exists
            cursor.execute(
                "SELECT index_id FROM indices WHERE index_code = ?",
                (index_code,)
            )
            result = cursor.fetchone()

            if result:
                # Update existing
                index_id = result[0]
                cursor.execute("""
                    UPDATE indices
                    SET index_name = ?, description = ?, country = ?,
                        data_source = ?, asset_class = ?, last_updated = ?
                    WHERE index_id = ?
                """, (index_name, description, country, data_source, asset_class,
                      datetime.now(), index_id))
                logger.info(f"Updated index {index_code} (id={index_id})")
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO indices (index_code, index_name, description,
                                       country, data_source, asset_class)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (index_code, index_name, description, country, data_source, asset_class))
                index_id = cursor.lastrowid
                logger.info(f"Registered new index {index_code} (id={index_id})")

            self.conn.commit()
            return index_id

        except sqlite3.Error as e:
            self.conn.rollback()
            raise DatabaseError(f"Failed to register index {index_code}: {e}")

    def get_index_id(self, index_code: str) -> Optional[int]:
        """
        Get index_id from index_code.

        Args:
            index_code: Index code (e.g., 'SP500')

        Returns:
            index_id or None if not found
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT index_id FROM indices WHERE index_code = ?",
                (index_code,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get index_id for {index_code}: {e}")

    def get_current_constituents(self, index_code: str) -> pd.DataFrame:
        """
        Get current constituents (end_date IS NULL).

        Args:
            index_code: Index code (e.g., 'SP500')

        Returns:
            DataFrame with current constituents
        """
        try:
            query = """
                SELECT
                    c.symbol,
                    c.company_name,
                    c.sector,
                    c.sub_industry,
                    c.date_added_to_index,
                    c.effective_date,
                    c.extracted_at,
                    c.data_source
                FROM index_constituents c
                JOIN indices i ON c.index_id = i.index_id
                WHERE i.index_code = ? AND c.end_date IS NULL
                ORDER BY c.symbol
            """
            df = pd.read_sql_query(query, self.conn, params=(index_code,))

            # Parse dates
            if 'date_added_to_index' in df.columns:
                df['date_added_to_index'] = pd.to_datetime(df['date_added_to_index'], errors='coerce')
            if 'effective_date' in df.columns:
                df['effective_date'] = pd.to_datetime(df['effective_date'], errors='coerce')
            if 'extracted_at' in df.columns:
                df['extracted_at'] = pd.to_datetime(df['extracted_at'], errors='coerce')

            return df
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get current constituents for {index_code}: {e}")

    def get_historical_constituents(self, index_code: str, as_of_date: str) -> pd.DataFrame:
        """
        Get constituents as of a specific date.

        Args:
            index_code: Index code (e.g., 'SP500')
            as_of_date: Date string (YYYY-MM-DD)

        Returns:
            DataFrame with constituents as of that date
        """
        try:
            query = """
                SELECT
                    c.symbol,
                    c.company_name,
                    c.sector,
                    c.sub_industry,
                    c.date_added_to_index,
                    c.effective_date,
                    c.end_date
                FROM index_constituents c
                JOIN indices i ON c.index_id = i.index_id
                WHERE i.index_code = ?
                  AND c.effective_date <= ?
                  AND (c.end_date IS NULL OR c.end_date > ?)
                ORDER BY c.symbol
            """
            df = pd.read_sql_query(query, self.conn, params=(index_code, as_of_date, as_of_date))

            # Parse dates
            for col in ['date_added_to_index', 'effective_date', 'end_date']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

            return df
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get historical constituents for {index_code}: {e}")

    def update_constituents(
        self,
        index_code: str,
        constituents_df: pd.DataFrame,
        extracted_at: Optional[datetime] = None,
        effective_date: Optional[date] = None
    ) -> Dict:
        """
        Update constituents with change detection.

        Logic:
        1. Get current constituents from DB
        2. Compare with new data
        3. Close out removed constituents (set end_date)
        4. Add new constituents
        5. Return summary of changes

        Args:
            index_code: Index code
            constituents_df: DataFrame with new constituents
            extracted_at: When data was extracted (default: now)
            effective_date: When changes become effective (default: today)

        Returns:
            Dict with summary: {
                'added_count': int,
                'removed_count': int,
                'unchanged_count': int,
                'added_symbols': list,
                'removed_symbols': list
            }
        """
        if extracted_at is None:
            extracted_at = datetime.now()
        if effective_date is None:
            effective_date = date.today()

        # Get index_id
        index_id = self.get_index_id(index_code)
        if index_id is None:
            raise DatabaseError(f"Index {index_code} not registered")

        # Get current constituents
        current_df = self.get_current_constituents(index_code)
        current_symbols = set(current_df['symbol'].tolist()) if not current_df.empty else set()

        # New symbols
        new_symbols = set(constituents_df['symbol'].tolist())

        # Detect changes
        added_symbols = new_symbols - current_symbols
        removed_symbols = current_symbols - new_symbols
        unchanged_symbols = current_symbols & new_symbols

        try:
            cursor = self.conn.cursor()

            # Close out removed constituents
            if removed_symbols:
                placeholders = ','.join(['?'] * len(removed_symbols))
                cursor.execute(f"""
                    UPDATE index_constituents
                    SET end_date = ?
                    WHERE index_id = ? AND symbol IN ({placeholders}) AND end_date IS NULL
                """, (effective_date, index_id, *removed_symbols))
                logger.info(f"Closed out {len(removed_symbols)} removed constituents")

            # Add new constituents
            data_source = constituents_df.iloc[0].get('source', 'wikipedia') if not constituents_df.empty else 'wikipedia'

            for symbol in added_symbols:
                row = constituents_df[constituents_df['symbol'] == symbol].iloc[0]

                cursor.execute("""
                    INSERT INTO index_constituents (
                        index_id, symbol, effective_date, end_date,
                        company_name, sector, sub_industry, date_added_to_index,
                        extracted_at, data_source
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """, (
                    index_id,
                    symbol,
                    effective_date,
                    row.get('company_name'),
                    row.get('sector'),
                    row.get('sub_industry'),
                    _convert_timestamp(row.get('date_added_to_index')),
                    extracted_at,
                    data_source
                ))

            logger.info(f"Added {len(added_symbols)} new constituents")

            # Update last_updated for index
            cursor.execute(
                "UPDATE indices SET last_updated = ? WHERE index_id = ?",
                (datetime.now(), index_id)
            )

            self.conn.commit()

        except sqlite3.Error as e:
            self.conn.rollback()
            raise DatabaseError(f"Failed to update constituents for {index_code}: {e}")

        return {
            'added_count': len(added_symbols),
            'removed_count': len(removed_symbols),
            'unchanged_count': len(unchanged_symbols),
            'added_symbols': sorted(list(added_symbols)),
            'removed_symbols': sorted(list(removed_symbols))
        }

    def list_indices(self) -> pd.DataFrame:
        """
        List all registered indices.

        Returns:
            DataFrame with index information
        """
        try:
            query = """
                SELECT
                    index_code,
                    index_name,
                    description,
                    country,
                    asset_class,
                    data_source,
                    created_at,
                    last_updated
                FROM indices
                ORDER BY index_code
            """
            df = pd.read_sql_query(query, self.conn)

            # Parse timestamps
            for col in ['created_at', 'last_updated']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')

            return df
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to list indices: {e}")

    def is_index_member(
        self,
        symbol: str,
        index_code: str,
        check_date: Optional[str] = None
    ) -> bool:
        """
        Check if symbol was in index on a specific date.

        Args:
            symbol: Stock symbol
            index_code: Index code
            check_date: Date to check (default: today)

        Returns:
            True if symbol was member on that date
        """
        if check_date is None:
            check_date = date.today().isoformat()

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*)
                FROM index_constituents c
                JOIN indices i ON c.index_id = i.index_id
                WHERE i.index_code = ?
                  AND c.symbol = ?
                  AND c.effective_date <= ?
                  AND (c.end_date IS NULL OR c.end_date > ?)
            """, (index_code, symbol, check_date, check_date))

            count = cursor.fetchone()[0]
            return count > 0
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to check membership for {symbol}: {e}")

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
            DataFrame with additions and removals
        """
        try:
            # Get additions
            query_added = """
                SELECT
                    c.effective_date as date,
                    'added' as change_type,
                    c.symbol,
                    c.company_name
                FROM index_constituents c
                JOIN indices i ON c.index_id = i.index_id
                WHERE i.index_code = ?
            """
            params_added = [index_code]

            if start_date:
                query_added += " AND c.effective_date >= ?"
                params_added.append(start_date)
            if end_date:
                query_added += " AND c.effective_date <= ?"
                params_added.append(end_date)

            # Get removals
            query_removed = """
                SELECT
                    c.end_date as date,
                    'removed' as change_type,
                    c.symbol,
                    c.company_name
                FROM index_constituents c
                JOIN indices i ON c.index_id = i.index_id
                WHERE i.index_code = ? AND c.end_date IS NOT NULL
            """
            params_removed = [index_code]

            if start_date:
                query_removed += " AND c.end_date >= ?"
                params_removed.append(start_date)
            if end_date:
                query_removed += " AND c.end_date <= ?"
                params_removed.append(end_date)

            # Combine
            query = f"{query_added} UNION ALL {query_removed} ORDER BY date DESC"
            params = params_added + params_removed

            df = pd.read_sql_query(query, self.conn, params=params)

            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')

            return df
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to get index changes for {index_code}: {e}")
