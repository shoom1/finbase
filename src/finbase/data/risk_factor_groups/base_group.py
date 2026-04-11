"""Base class for managing risk factor group definitions from JSON files."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class RiskFactorGroup:
    """Base class for managing risk factor group definitions from JSON files."""

    def __init__(self, group_path: str):
        """
        Initialize risk factor group from JSON file.

        Args:
            group_path: Path to JSON file, e.g., "data/risk_factor_groups/equities/sp500.json"
        """
        self.group_path = Path(group_path)
        self.config = self.load()

    def load(self) -> Dict:
        """Load group configuration from JSON."""
        if not self.group_path.exists():
            raise FileNotFoundError(f"Risk factor group file not found: {self.group_path}")

        with open(self.group_path, 'r') as f:
            return json.load(f)

    def save(self):
        """Save current configuration back to JSON."""
        self.config['last_updated'] = datetime.now().strftime('%Y-%m-%d')

        with open(self.group_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get_symbols(self) -> List[str]:
        """Return list of symbols in this group."""
        return [rf['symbol'] for rf in self.config['risk_factors']]

    def get_metadata(self) -> Dict:
        """Return group metadata (asset_class, data_source, etc.)"""
        return {
            'group_name': self.config['group_name'],
            'description': self.config.get('description', ''),
            'asset_class': self.config['asset_class'],
            'asset_subclass': self.config.get('asset_subclass'),
            'data_source': self.config['data_source'],
            'frequency': self.config['frequency'],
            'last_updated': self.config['last_updated']
        }

    def get_risk_factor(self, symbol: str) -> Optional[Dict]:
        """
        Get full details for a specific risk factor.

        Args:
            symbol: Symbol to look up

        Returns:
            Dictionary with risk factor details, or None if not found
        """
        for rf in self.config['risk_factors']:
            if rf['symbol'] == symbol:
                return rf
        return None

    def filter_by(self, **kwargs) -> List[str]:
        """
        Filter risk factors by attributes.

        Examples:
            filter_by(sector='Technology')
            filter_by(country='US', market_cap_category='mega')

        Args:
            **kwargs: Attribute filters

        Returns:
            List of symbols matching all filters
        """
        filtered = []
        for rf in self.config['risk_factors']:
            match = True
            for key, value in kwargs.items():
                if rf.get(key) != value:
                    match = False
                    break
            if match:
                filtered.append(rf['symbol'])
        return filtered

    def count(self) -> int:
        """Return number of risk factors in this group."""
        return len(self.config['risk_factors'])

    def __repr__(self) -> str:
        """String representation."""
        meta = self.get_metadata()
        return f"RiskFactorGroup('{meta['group_name']}', {self.count()} factors, {meta['asset_class']})"

    def __len__(self) -> int:
        """Return count of risk factors."""
        return self.count()
