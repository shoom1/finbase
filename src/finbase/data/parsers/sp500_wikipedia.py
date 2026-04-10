"""
Parser for S&P 500 company data from Wikipedia.

Extracts current constituents and historical changes from:
https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
"""

import pandas as pd
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from io import StringIO

from ...utils.logging import get_logger

logger = get_logger(__name__)


class SP500ParserError(Exception):
    """Exception raised for S&P 500 parser errors."""
    pass


class SP500WikipediaParser:
    """
    Parser for S&P 500 company data from Wikipedia.

    Extracts:
    1. Current constituents (ticker, company name, sector, date added, etc.)
    2. Historical changes (additions and removals with dates)
    """

    WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def __init__(self, url: Optional[str] = None):
        """
        Initialize the parser.

        Args:
            url: Optional custom URL (default: Wikipedia S&P 500 page)
        """
        self.url = url or self.WIKIPEDIA_URL
        self._html_content = None
        self._tables = None

    def fetch_page(self) -> str:
        """
        Fetch the Wikipedia page content.

        Returns:
            HTML content as string

        Raises:
            SP500ParserError: If page fetch fails
        """
        try:
            logger.info(f"Fetching S&P 500 data from {self.url}")

            # Set User-Agent to avoid 403 errors from Wikipedia
            headers = {
                'User-Agent': 'FinBase/0.1.0 (Financial Data Management; Educational/Research Use)'
            }

            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            self._html_content = response.text
            logger.info("Successfully fetched S&P 500 Wikipedia page")
            return self._html_content
        except Exception as e:
            raise SP500ParserError(f"Failed to fetch Wikipedia page: {e}")

    def _parse_tables(self) -> List[pd.DataFrame]:
        """
        Parse all tables from the HTML content.

        Returns:
            List of DataFrames, one per table

        Raises:
            SP500ParserError: If parsing fails
        """
        if self._html_content is None:
            self.fetch_page()

        try:
            # Use pandas to parse HTML tables
            tables = pd.read_html(StringIO(self._html_content))
            logger.info(f"Found {len(tables)} tables in Wikipedia page")
            self._tables = tables
            return tables
        except Exception as e:
            raise SP500ParserError(f"Failed to parse HTML tables: {e}")

    def get_current_constituents(self) -> pd.DataFrame:
        """
        Extract current S&P 500 constituents.

        Returns:
            DataFrame with columns:
                - Symbol: Stock ticker
                - Security: Company name
                - GICS Sector: Sector classification
                - GICS Sub-Industry: Sub-industry classification
                - Headquarters Location: Company headquarters
                - Date added: Date added to S&P 500
                - CIK: Central Index Key
                - Founded: Year founded

        Raises:
            SP500ParserError: If extraction fails
        """
        if self._tables is None:
            self._parse_tables()

        try:
            # The first table is typically the current constituents
            constituents = self._tables[0].copy()

            logger.info(f"Extracted {len(constituents)} current S&P 500 constituents")
            logger.info(f"Columns: {constituents.columns.tolist()}")

            # Standardize column names if needed
            column_mapping = {
                'Symbol': 'symbol',
                'Security': 'company_name',
                'GICS Sector': 'sector',
                'GICS Sub-Industry': 'sub_industry',
                'Headquarters Location': 'headquarters',
                'Date added': 'date_added',
                'CIK': 'cik',
                'Founded': 'founded'
            }

            # Rename columns that exist
            rename_dict = {k: v for k, v in column_mapping.items() if k in constituents.columns}
            constituents = constituents.rename(columns=rename_dict)

            # Clean and standardize data
            if 'symbol' in constituents.columns:
                # Remove any whitespace and convert to uppercase
                constituents['symbol'] = constituents['symbol'].str.strip().str.upper()

            if 'date_added' in constituents.columns:
                # Parse dates (handle various formats)
                constituents['date_added'] = pd.to_datetime(
                    constituents['date_added'],
                    errors='coerce'
                )

            # Add metadata
            constituents['extracted_at'] = datetime.now()
            constituents['source'] = 'wikipedia'

            return constituents

        except Exception as e:
            raise SP500ParserError(f"Failed to extract current constituents: {e}")

    def get_historical_changes(self) -> pd.DataFrame:
        """
        Extract historical changes (additions and removals).

        Returns:
            DataFrame with columns:
                - Date: Change date
                - Added_Ticker: Ticker of added company (or NaN)
                - Added_Security: Name of added company (or NaN)
                - Removed_Ticker: Ticker of removed company (or NaN)
                - Removed_Security: Name of removed company (or NaN)
                - Reason: Reason for change

        Raises:
            SP500ParserError: If extraction fails
        """
        if self._tables is None:
            self._parse_tables()

        try:
            # The second table is typically the historical changes
            # Format varies, but usually has Date, Added (Ticker/Security), Removed (Ticker/Security), Reason
            if len(self._tables) < 2:
                logger.warning("No historical changes table found")
                return pd.DataFrame()

            changes = self._tables[1].copy()

            logger.info(f"Extracted {len(changes)} historical changes")
            logger.info(f"Columns: {changes.columns.tolist()}")

            # Handle multi-level column headers if present
            if isinstance(changes.columns, pd.MultiIndex):
                # Flatten multi-index columns
                changes.columns = ['_'.join(col).strip() if col[1] else col[0]
                                  for col in changes.columns.values]
                logger.info(f"Flattened multi-index columns: {changes.columns.tolist()}")

            # Standardize column names
            # Include both original names and flattened multi-index names
            column_mapping = {
                # Original single-level names
                'Date': 'date',
                'Added Ticker': 'added_ticker',
                'Added Security': 'added_company',
                'Removed Ticker': 'removed_ticker',
                'Removed Security': 'removed_company',
                'Reason': 'reason',
                # Flattened multi-index names (from Wikipedia's actual format)
                'Effective Date_Effective Date': 'date',
                'Added_Ticker': 'added_ticker',
                'Added_Security': 'added_company',
                'Removed_Ticker': 'removed_ticker',
                'Removed_Security': 'removed_company',
                'Reason_Reason': 'reason'
            }

            # Attempt to rename columns
            rename_dict = {k: v for k, v in column_mapping.items() if k in changes.columns}
            changes = changes.rename(columns=rename_dict)
            logger.info(f"Renamed columns: {changes.columns.tolist()}")

            # Parse dates
            if 'date' in changes.columns:
                changes['date'] = pd.to_datetime(changes['date'], errors='coerce')

            # Clean ticker symbols
            for col in ['added_ticker', 'removed_ticker']:
                if col in changes.columns:
                    changes[col] = changes[col].str.strip().str.upper()
                    # Replace empty strings with NaN
                    changes[col] = changes[col].replace('', pd.NA)

            # Add metadata
            changes['extracted_at'] = datetime.now()
            changes['source'] = 'wikipedia'

            # Sort by date (most recent first)
            if 'date' in changes.columns:
                changes = changes.sort_values('date', ascending=False)

            return changes

        except Exception as e:
            raise SP500ParserError(f"Failed to extract historical changes: {e}")

    def get_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get both current constituents and historical changes.

        Returns:
            Tuple of (constituents_df, changes_df)
        """
        constituents = self.get_current_constituents()
        changes = self.get_historical_changes()
        return constituents, changes

    def export_to_csv(self, output_dir: str = ".", prefix: str = "sp500") -> Dict[str, str]:
        """
        Export data to CSV files.

        Args:
            output_dir: Directory to save CSV files
            prefix: Prefix for filenames

        Returns:
            Dict mapping data type to file path
        """
        import os

        constituents, changes = self.get_all_data()

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filenames with timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        constituents_file = os.path.join(output_dir, f"{prefix}_constituents_{timestamp}.csv")
        changes_file = os.path.join(output_dir, f"{prefix}_changes_{timestamp}.csv")

        # Export
        constituents.to_csv(constituents_file, index=False)
        changes.to_csv(changes_file, index=False)

        logger.info(f"Exported constituents to {constituents_file}")
        logger.info(f"Exported changes to {changes_file}")

        return {
            'constituents': constituents_file,
            'changes': changes_file
        }

    def export_to_json(self, output_dir: str = ".", prefix: str = "sp500") -> Dict[str, str]:
        """
        Export data to JSON files.

        Args:
            output_dir: Directory to save JSON files
            prefix: Prefix for filenames

        Returns:
            Dict mapping data type to file path
        """
        import os

        constituents, changes = self.get_all_data()

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filenames with timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        constituents_file = os.path.join(output_dir, f"{prefix}_constituents_{timestamp}.json")
        changes_file = os.path.join(output_dir, f"{prefix}_changes_{timestamp}.json")

        # Export (orient='records' for list of dicts)
        constituents.to_json(constituents_file, orient='records', date_format='iso', indent=2)
        changes.to_json(changes_file, orient='records', date_format='iso', indent=2)

        logger.info(f"Exported constituents to {constituents_file}")
        logger.info(f"Exported changes to {changes_file}")

        return {
            'constituents': constituents_file,
            'changes': changes_file
        }

    def get_summary_stats(self) -> Dict:
        """
        Get summary statistics about S&P 500 data.

        Returns:
            Dict with summary statistics
        """
        constituents, changes = self.get_all_data()

        stats = {
            'total_constituents': len(constituents),
            'sectors': {},
            'total_changes': len(changes),
            'recent_additions': [],
            'recent_removals': [],
            'data_date': datetime.now().isoformat()
        }

        # Sector breakdown
        if 'sector' in constituents.columns:
            stats['sectors'] = constituents['sector'].value_counts().to_dict()

        # Recent changes (last 10)
        if not changes.empty:
            recent = changes.head(10)

            if 'added_ticker' in recent.columns:
                additions = recent[recent['added_ticker'].notna()][
                    ['date', 'added_ticker', 'added_company']
                ].head(5)
                stats['recent_additions'] = additions.to_dict('records')

            if 'removed_ticker' in recent.columns:
                removals = recent[recent['removed_ticker'].notna()][
                    ['date', 'removed_ticker', 'removed_company']
                ].head(5)
                stats['recent_removals'] = removals.to_dict('records')

        return stats
