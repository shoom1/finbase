"""
Orchestrates index constituent updates from parsers to database.

This module coordinates fetching index data from external sources (Wikipedia)
and updating the database with change detection.
"""

from datetime import datetime, date
from typing import Dict, Optional

from .database.index_db import IndexDB
from .parsers.wikipedia_index_parser import WikipediaIndexParser, WikipediaIndexParserError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class IndexUpdaterError(Exception):
    """Exception raised for index updater errors."""
    pass


class IndexUpdater:
    """
    Updates index constituents from external sources.

    Orchestrates:
    1. Loading parser configuration
    2. Fetching data from source (Wikipedia)
    3. Registering index if new
    4. Updating database with change detection
    5. Logging summary of changes
    """

    def __init__(self, index_db: IndexDB):
        """
        Initialize updater with IndexDB instance.

        Args:
            index_db: IndexDB instance for database operations
        """
        self.index_db = index_db

    def update_from_wikipedia(
        self,
        index_code: str,
        force: bool = False,
        effective_date: Optional[date] = None
    ) -> Dict:
        """
        Update index from Wikipedia.

        Args:
            index_code: Index code (e.g., 'SP500', 'DOW30')
            force: Force update even if recently updated
            effective_date: When changes become effective (default: today)

        Returns:
            Dict with summary:
                {
                    'index_code': str,
                    'index_name': str,
                    'total_constituents': int,
                    'added_count': int,
                    'removed_count': int,
                    'unchanged_count': int,
                    'added_symbols': list,
                    'removed_symbols': list,
                    'extraction_time': str,
                    'data_source': str
                }

        Raises:
            IndexUpdaterError: If update fails
        """
        try:
            logger.info(f"Starting update for {index_code} from Wikipedia")

            # 1. Load parser configuration and fetch data
            try:
                parser = WikipediaIndexParser.from_index_code(index_code)
            except WikipediaIndexParserError as e:
                raise IndexUpdaterError(f"Failed to load parser for {index_code}: {e}")

            # 2. Fetch and parse constituents
            try:
                constituents_df = parser.get_constituents()
                logger.info(f"Fetched {len(constituents_df)} constituents for {index_code}")
            except WikipediaIndexParserError as e:
                raise IndexUpdaterError(f"Failed to fetch constituents for {index_code}: {e}")

            # 3. Register index if not exists
            config = parser.config
            try:
                index_id = self.index_db.register_index(
                    index_code=config['index_code'],
                    index_name=config['index_name'],
                    description=config.get('description', ''),
                    country=config.get('country', 'US'),
                    data_source=config.get('data_source', 'wikipedia'),
                    asset_class=config.get('asset_class', 'equity')
                )
                logger.info(f"Registered/updated index {index_code} (id={index_id})")
            except Exception as e:
                raise IndexUpdaterError(f"Failed to register index {index_code}: {e}")

            # 4. Update database with change detection
            try:
                changes = self.index_db.update_constituents(
                    index_code=index_code,
                    constituents_df=constituents_df,
                    extracted_at=datetime.now(),
                    effective_date=effective_date
                )
                logger.info(
                    f"Updated {index_code}: "
                    f"+{changes['added_count']} constituents, "
                    f"-{changes['removed_count']} constituents, "
                    f"={changes['unchanged_count']} unchanged"
                )
            except Exception as e:
                raise IndexUpdaterError(f"Failed to update constituents for {index_code}: {e}")

            # 5. Build summary report
            summary = {
                'index_code': index_code,
                'index_name': config['index_name'],
                'total_constituents': len(constituents_df),
                'added_count': changes['added_count'],
                'removed_count': changes['removed_count'],
                'unchanged_count': changes['unchanged_count'],
                'added_symbols': changes['added_symbols'],
                'removed_symbols': changes['removed_symbols'],
                'extraction_time': datetime.now().isoformat(),
                'data_source': config.get('data_source', 'wikipedia'),
                'url': config.get('url', '')
            }

            # Log details if there were changes
            if changes['added_count'] > 0:
                logger.info(f"Added symbols: {', '.join(changes['added_symbols'][:10])}" +
                           (f" and {changes['added_count'] - 10} more" if changes['added_count'] > 10 else ""))
            if changes['removed_count'] > 0:
                logger.info(f"Removed symbols: {', '.join(changes['removed_symbols'][:10])}" +
                           (f" and {changes['removed_count'] - 10} more" if changes['removed_count'] > 10 else ""))

            logger.info(f"Successfully completed update for {index_code}")
            return summary

        except IndexUpdaterError:
            raise
        except Exception as e:
            raise IndexUpdaterError(f"Unexpected error updating {index_code}: {e}")

    def update_all_configured_indices(self, force: bool = False) -> Dict[str, Dict]:
        """
        Update all indices that have config files.

        Args:
            force: Force update even if recently updated

        Returns:
            Dict mapping index_code to summary dict
        """
        from pathlib import Path
        import json

        # Find all config files
        config_dir = Path(__file__).parent.parent.parent / "data" / "index_configs"
        config_files = list(config_dir.glob("*.json"))

        if not config_files:
            logger.warning(f"No index config files found in {config_dir}")
            return {}

        logger.info(f"Found {len(config_files)} index configs to update")

        results = {}
        for config_file in config_files:
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                index_code = config.get('index_code')

                if not index_code:
                    logger.warning(f"No index_code in config {config_file}, skipping")
                    continue

                logger.info(f"Updating {index_code}...")
                summary = self.update_from_wikipedia(index_code, force=force)
                results[index_code] = summary

            except Exception as e:
                logger.error(f"Failed to update {config_file.stem}: {e}")
                results[config_file.stem] = {
                    'error': str(e),
                    'status': 'failed'
                }

        return results

    def get_update_summary(self, index_code: str) -> Optional[Dict]:
        """
        Get summary of last update for an index.

        Args:
            index_code: Index code

        Returns:
            Dict with summary info or None if index not found
        """
        try:
            indices_df = self.index_db.list_indices()
            if indices_df.empty:
                return None

            index_row = indices_df[indices_df['index_code'] == index_code]
            if index_row.empty:
                return None

            row = index_row.iloc[0]
            constituents_df = self.index_db.get_current_constituents(index_code)

            return {
                'index_code': row['index_code'],
                'index_name': row['index_name'],
                'total_constituents': len(constituents_df),
                'last_updated': row.get('last_updated'),
                'data_source': row.get('data_source'),
                'country': row.get('country')
            }
        except Exception as e:
            logger.error(f"Failed to get update summary for {index_code}: {e}")
            return None
