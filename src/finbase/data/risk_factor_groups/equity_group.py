"""Manager for equity risk factor groups with auto-update capabilities."""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import List
from .base_group import RiskFactorGroup
from ...utils.logging import get_logger

logger = get_logger(__name__)


class EquityRiskFactorGroup(RiskFactorGroup):
    """Manager for equity risk factor groups with auto-update capabilities."""

    def update_from_wikipedia_sp500(self):
        """
        Update S&P 500 constituents from Wikipedia.
        Automatically fetches current list.

        Returns:
            List of risk factor dictionaries
        """
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

        logger.info("Fetching S&P 500 constituents from Wikipedia...")

        # Fetch table
        tables = pd.read_html(url)
        df = tables[0]  # First table is constituents

        # Build risk factors list
        new_risk_factors = []
        for _, row in df.iterrows():
            rf_data = {
                'symbol': row['Symbol'].replace('.', '-'),  # YFinance format
                'description': row['Security'],
                'country': 'US',
                'currency': 'USD',
                'sector': row['GICS Sector'],
                'sub_industry': row['GICS Sub-Industry'],
                'headquarters': row['Headquarters Location'],
                'date_added': str(row.get('Date added', '')),
                'cik': str(row.get('CIK', '')),
                'founded': str(row.get('Founded', ''))
            }
            new_risk_factors.append(rf_data)

        # Update config
        self.config['risk_factors'] = new_risk_factors
        self.config['last_updated'] = datetime.now().strftime('%Y-%m-%d')

        # Save
        self.save()

        logger.info(f"Updated S&P 500: {len(new_risk_factors)} risk factors")
        return new_risk_factors

    def update_market_caps(self, batch_size: int = 50):
        """
        Update market cap categories (mega/large/mid/small) for all risk factors.
        Uses YFinance to fetch current market caps.

        Args:
            batch_size: Number of symbols to process before saving (for progress tracking)
        """
        import yfinance as yf

        total = len(self.config['risk_factors'])
        logger.info(f"Updating market caps for {total} symbols...")

        for i, rf_data in enumerate(self.config['risk_factors']):
            symbol = rf_data['symbol']
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                market_cap = info.get('marketCap', 0)

                # Categorize
                if market_cap > 200e9:
                    category = 'mega'
                elif market_cap > 10e9:
                    category = 'large'
                elif market_cap > 2e9:
                    category = 'mid'
                else:
                    category = 'small'

                rf_data['market_cap'] = market_cap
                rf_data['market_cap_category'] = category

                if (i + 1) % 10 == 0:
                    logger.info(f"  Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")

                # Save periodically
                if (i + 1) % batch_size == 0:
                    self.save()
                    logger.info(f"  Saved progress at {i+1} symbols")

            except Exception as e:
                logger.warning(f"Error fetching market cap for {symbol}: {e}")
                # Set default values
                rf_data['market_cap'] = None
                rf_data['market_cap_category'] = 'unknown'

        # Final save
        self.save()
        logger.info("Market cap update complete")

    def get_top_n_by_market_cap(self, n: int = 100) -> List[str]:
        """
        Get top N symbols by market cap.
        Useful for creating "S&P 500 Top 100" subsets.

        Args:
            n: Number of top symbols to return

        Returns:
            List of symbols sorted by market cap (descending)
        """
        # Sort by market cap
        rfs_with_cap = [
            rf for rf in self.config['risk_factors']
            if 'market_cap' in rf and rf['market_cap'] is not None and rf['market_cap'] > 0
        ]
        rfs_with_cap.sort(key=lambda x: x['market_cap'], reverse=True)

        return [rf['symbol'] for rf in rfs_with_cap[:n]]

    def create_sector_subset(self, sector: str, output_path: str):
        """
        Create a new JSON file with only stocks from specific sector.

        Example:
            create_sector_subset('Technology', 'data/risk_factor_groups/equities/sectors/technology.json')

        Args:
            sector: Sector name (e.g., 'Technology', 'Financials')
            output_path: Path to output JSON file
        """
        sector_rfs = [
            rf for rf in self.config['risk_factors']
            if rf.get('sector') == sector
        ]

        if not sector_rfs:
            logger.warning(f"No risk factors found for sector '{sector}'")
            return

        sector_config = {
            'group_name': f"sp500_{sector.lower().replace(' ', '_')}",
            'description': f"S&P 500 {sector} sector stocks",
            'asset_class': 'equity',
            'asset_subclass': 'stock',
            'data_source': self.config['data_source'],
            'frequency': self.config['frequency'],
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'parent_group': self.config['group_name'],
            'sector_filter': sector,
            'risk_factors': sector_rfs
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(sector_config, f, indent=2)

        logger.info(f"Created {sector} sector group: {len(sector_rfs)} stocks -> {output_path}")

    def create_market_cap_subset(self, category: str, output_path: str):
        """
        Create a new JSON file with only stocks from specific market cap category.

        Args:
            category: Market cap category ('mega', 'large', 'mid', 'small')
            output_path: Path to output JSON file
        """
        cap_rfs = [
            rf for rf in self.config['risk_factors']
            if rf.get('market_cap_category') == category
        ]

        if not cap_rfs:
            logger.warning(f"No risk factors found for market cap category '{category}'")
            return

        cap_config = {
            'group_name': f"sp500_{category}_cap",
            'description': f"S&P 500 {category}-cap stocks",
            'asset_class': 'equity',
            'asset_subclass': 'stock',
            'data_source': self.config['data_source'],
            'frequency': self.config['frequency'],
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'parent_group': self.config['group_name'],
            'market_cap_filter': category,
            'risk_factors': cap_rfs
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(cap_config, f, indent=2)

        logger.info(f"Created {category}-cap group: {len(cap_rfs)} stocks -> {output_path}")
