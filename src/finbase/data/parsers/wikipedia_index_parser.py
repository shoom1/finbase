"""
Generic Wikipedia parser for equity index constituents.

This parser uses configuration files to extract index constituent data
from Wikipedia pages. It's designed to work with multiple indices (S&P 500,
Dow 30, NASDAQ-100, etc.) without code changes.
"""

import pandas as pd
import requests
import json
import os
from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime
from io import StringIO

from ...utils.logging import get_logger

logger = get_logger(__name__)


class WikipediaIndexParserError(Exception):
    """Exception raised for Wikipedia index parser errors."""
    pass


class WikipediaIndexParser:
    """
    Generic parser for index constituents from Wikipedia.

    Uses JSON configuration files to handle different Wikipedia table formats.
    Each index has its own config file in data/index_configs/.
    """

    def __init__(self, config: Dict):
        """
        Initialize parser with configuration.

        Args:
            config: Configuration dictionary with keys:
                - index_code: Unique code (e.g., 'SP500')
                - index_name: Full name
                - url: Wikipedia URL
                - constituents_table: Table config
                - changes_table: Changes table config (optional)
        """
        self.config = config
        self.index_code = config['index_code']
        self.url = config['url']
        self._html_content = None
        self._tables = None

    @classmethod
    def from_index_code(cls, index_code: str):
        """
        Create parser from index code by loading config file.

        Args:
            index_code: Index code (e.g., 'SP500', 'DOW30')

        Returns:
            WikipediaIndexParser instance

        Raises:
            WikipediaIndexParserError: If config file not found
        """
        from importlib.resources import files

        config_dir = files("finbase.index_configs")
        config_file = config_dir / f"{index_code.lower()}.json"

        try:
            config_text = config_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise WikipediaIndexParserError(
                f"Config file not found for {index_code}. "
                f"Expected: {index_code.lower()}.json in finbase/index_configs/"
            )

        try:
            config = json.loads(config_text)
            logger.info(f"Loaded config for {index_code}")
            return cls(config)
        except json.JSONDecodeError as e:
            raise WikipediaIndexParserError(f"Invalid JSON in config for {index_code}: {e}")

    @classmethod
    def from_config_file(cls, config_path: str):
        """
        Create parser from config file path.

        Args:
            config_path: Path to JSON config file

        Returns:
            WikipediaIndexParser instance
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return cls(config)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            raise WikipediaIndexParserError(f"Failed to load config from {config_path}: {e}")

    def fetch_page(self) -> str:
        """
        Fetch the Wikipedia page content.

        Returns:
            HTML content as string

        Raises:
            WikipediaIndexParserError: If page fetch fails
        """
        try:
            logger.info(f"Fetching {self.index_code} data from {self.url}")

            # Set User-Agent to avoid 403 errors
            headers = {
                'User-Agent': 'FinBase/0.1.0 (Financial Data Management; Educational/Research Use)'
            }

            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            self._html_content = response.text
            logger.info(f"Successfully fetched {self.index_code} Wikipedia page")
            return self._html_content
        except requests.RequestException as e:
            raise WikipediaIndexParserError(f"Failed to fetch Wikipedia page for {self.index_code}: {e}")

    def _parse_tables(self) -> List[pd.DataFrame]:
        """
        Parse all tables from the HTML content.

        Returns:
            List of DataFrames, one per table

        Raises:
            WikipediaIndexParserError: If parsing fails
        """
        if self._html_content is None:
            self.fetch_page()

        try:
            # Use pandas to parse HTML tables
            tables = pd.read_html(StringIO(self._html_content))
            logger.info(f"Found {len(tables)} tables in {self.index_code} Wikipedia page")
            self._tables = tables
            return tables
        except Exception as e:
            raise WikipediaIndexParserError(f"Failed to parse HTML tables for {self.index_code}: {e}")

    def get_constituents(self) -> pd.DataFrame:
        """
        Extract current constituents using config mapping.

        Returns:
            DataFrame with standardized column names

        Raises:
            WikipediaIndexParserError: If extraction fails
        """
        if self._tables is None:
            self._parse_tables()

        try:
            table_config = self.config.get('constituents_table')
            if not table_config:
                raise WikipediaIndexParserError(f"No constituents_table config for {self.index_code}")

            table_index = table_config['table_index']
            column_mapping = table_config['column_mapping']

            # Get the table
            if table_index >= len(self._tables):
                raise WikipediaIndexParserError(
                    f"Table index {table_index} out of range. Found {len(self._tables)} tables."
                )

            constituents = self._tables[table_index].copy()
            logger.info(f"Extracted table {table_index} with {len(constituents)} rows")
            logger.debug(f"Original columns: {constituents.columns.tolist()}")

            # Apply column mapping
            rename_dict = {k: v for k, v in column_mapping.items() if k in constituents.columns}
            constituents = constituents.rename(columns=rename_dict)

            # Ensure required columns
            if 'symbol' not in constituents.columns:
                raise WikipediaIndexParserError(
                    f"Required 'symbol' column not found after mapping. "
                    f"Available columns: {constituents.columns.tolist()}"
                )

            # Clean symbol column
            constituents['symbol'] = constituents['symbol'].str.strip().str.upper()

            # Clean company_name if present
            if 'company_name' in constituents.columns:
                constituents['company_name'] = constituents['company_name'].str.strip()

            # Parse date_added_to_index if present
            if 'date_added_to_index' in constituents.columns:
                constituents['date_added_to_index'] = pd.to_datetime(
                    constituents['date_added_to_index'],
                    errors='coerce'
                )

            # Add metadata
            constituents['extracted_at'] = datetime.now()
            constituents['source'] = self.config.get('data_source', 'wikipedia')
            constituents['index_code'] = self.index_code

            logger.info(f"Extracted {len(constituents)} constituents for {self.index_code}")
            return constituents

        except Exception as e:
            raise WikipediaIndexParserError(f"Failed to extract constituents for {self.index_code}: {e}")

    def get_changes(self) -> Optional[pd.DataFrame]:
        """
        Extract historical changes if available.

        Returns:
            DataFrame with changes or None if not available

        Raises:
            WikipediaIndexParserError: If extraction fails
        """
        if self._tables is None:
            self._parse_tables()

        try:
            table_config = self.config.get('changes_table')
            if not table_config:
                logger.info(f"No changes_table config for {self.index_code}, skipping")
                return None

            table_index = table_config['table_index']
            column_mapping = table_config['column_mapping']
            has_multiindex = table_config.get('has_multiindex_columns', False)

            # Get the table
            if table_index >= len(self._tables):
                logger.warning(f"Changes table index {table_index} out of range, skipping")
                return None

            changes = self._tables[table_index].copy()
            logger.info(f"Extracted changes table {table_index} with {len(changes)} rows")

            # Handle multi-index columns if needed
            if has_multiindex and isinstance(changes.columns, pd.MultiIndex):
                # Flatten multi-index columns
                changes.columns = ['_'.join(col).strip() if col[1] else col[0]
                                  for col in changes.columns.values]
                logger.debug(f"Flattened multi-index columns: {changes.columns.tolist()}")

            # Apply column mapping
            rename_dict = {k: v for k, v in column_mapping.items() if k in changes.columns}
            changes = changes.rename(columns=rename_dict)

            # Parse date column if present
            if 'date' in changes.columns:
                changes['date'] = pd.to_datetime(changes['date'], errors='coerce')
                # Sort by date (most recent first)
                changes = changes.sort_values('date', ascending=False)

            # Clean ticker columns
            for col in ['added_ticker', 'removed_ticker']:
                if col in changes.columns:
                    changes[col] = changes[col].str.strip().str.upper()
                    changes[col] = changes[col].replace('', pd.NA)

            # Add metadata
            changes['extracted_at'] = datetime.now()
            changes['source'] = self.config.get('data_source', 'wikipedia')
            changes['index_code'] = self.index_code

            logger.info(f"Extracted {len(changes)} historical changes for {self.index_code}")
            return changes

        except Exception as e:
            logger.warning(f"Failed to extract changes for {self.index_code}: {e}")
            return None

    def get_all_data(self):
        """
        Get both constituents and changes.

        Returns:
            Tuple of (constituents_df, changes_df)
            changes_df may be None if not available
        """
        constituents = self.get_constituents()
        changes = self.get_changes()
        return constituents, changes

    def get_summary(self) -> Dict:
        """
        Get summary statistics.

        Returns:
            Dict with summary info
        """
        constituents = self.get_constituents()

        summary = {
            'index_code': self.index_code,
            'index_name': self.config['index_name'],
            'total_constituents': len(constituents),
            'extraction_time': datetime.now().isoformat(),
            'data_source': self.config.get('data_source', 'wikipedia'),
            'url': self.url
        }

        # Sector breakdown if available
        if 'sector' in constituents.columns:
            summary['sectors'] = constituents['sector'].value_counts().to_dict()

        # Country if available
        if 'country' in self.config:
            summary['country'] = self.config['country']

        return summary

    def get_summary_stats(self) -> Dict:
        """
        Richer summary including changes metadata.

        Builds on `get_summary()` and adds the historical-changes view —
        total change count, the five most recent additions and removals,
        and a `data_date` ISO timestamp. Indices without a changes table
        get empty lists for additions/removals and zero for total_changes.
        """
        summary = self.get_summary()
        summary['data_date'] = datetime.now().isoformat()

        changes = self.get_changes()
        if changes is None or changes.empty:
            summary['total_changes'] = 0
            summary['recent_additions'] = []
            summary['recent_removals'] = []
            return summary

        summary['total_changes'] = len(changes)

        recent = changes.head(10)
        if 'added_ticker' in recent.columns:
            additions = recent[recent['added_ticker'].notna()][
                [c for c in ('date', 'added_ticker', 'added_company') if c in recent.columns]
            ].head(5)
            summary['recent_additions'] = additions.to_dict('records')
        else:
            summary['recent_additions'] = []

        if 'removed_ticker' in recent.columns:
            removals = recent[recent['removed_ticker'].notna()][
                [c for c in ('date', 'removed_ticker', 'removed_company') if c in recent.columns]
            ].head(5)
            summary['recent_removals'] = removals.to_dict('records')
        else:
            summary['recent_removals'] = []

        return summary

    def export_to_csv(
        self,
        output_dir: str = ".",
        prefix: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Export constituents (and changes if available) to timestamped CSVs.

        Args:
            output_dir: Directory for output files. Created if missing.
            prefix: Filename prefix (default: lower-case index code, e.g. 'sp500').

        Returns:
            Dict mapping {'constituents': path, 'changes': path-or-None}.
        """
        return self._export(output_dir, prefix, fmt='csv')

    def export_to_json(
        self,
        output_dir: str = ".",
        prefix: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """JSON twin of `export_to_csv`. See that method for arguments."""
        return self._export(output_dir, prefix, fmt='json')

    def _export(
        self,
        output_dir: str,
        prefix: Optional[str],
        fmt: str,
    ) -> Dict[str, Optional[str]]:
        if prefix is None:
            prefix = self.index_code.lower()

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d")
        ext = fmt

        constituents = self.get_constituents()
        constituents_path = os.path.join(output_dir, f"{prefix}_constituents_{timestamp}.{ext}")
        if fmt == 'csv':
            constituents.to_csv(constituents_path, index=False)
        else:
            constituents.to_json(constituents_path, orient='records', date_format='iso', indent=2)
        logger.info(f"Exported {self.index_code} constituents to {constituents_path}")

        changes = self.get_changes()
        changes_path: Optional[str] = None
        if changes is not None and not changes.empty:
            changes_path = os.path.join(output_dir, f"{prefix}_changes_{timestamp}.{ext}")
            if fmt == 'csv':
                changes.to_csv(changes_path, index=False)
            else:
                changes.to_json(changes_path, orient='records', date_format='iso', indent=2)
            logger.info(f"Exported {self.index_code} changes to {changes_path}")

        return {'constituents': constituents_path, 'changes': changes_path}
