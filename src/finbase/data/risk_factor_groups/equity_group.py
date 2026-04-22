"""
Equity-specific helpers built on top of :class:`RiskFactorGroup`.

This class used to also do Wikipedia scraping (`update_from_wikipedia_sp500`)
and YFinance market-cap fetches (`update_market_caps`). H4 split those
responsibilities out:

- Wikipedia data → ``WikipediaIndexParser.from_index_code('SP500')``
- Market caps    → ``finbase.data.risk_factor_groups.market_cap_enricher.MarketCapEnricher``

What remains here are pure data operations on an already-loaded group:
sorting by market cap, and writing sector/cap subset files.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .base_group import RiskFactorGroup
from ...utils.logging import get_logger

logger = get_logger(__name__)


class EquityRiskFactorGroup(RiskFactorGroup):
    """Equity-specific operations on a loaded risk-factor group."""

    def get_top_n_by_market_cap(self, n: int = 100) -> List[str]:
        """
        Return symbols sorted by market cap (descending), limited to N.

        Requires market_cap to have been populated already (e.g. by
        :class:`MarketCapEnricher`). Symbols without a positive market_cap
        are skipped.
        """
        rfs_with_cap = [
            rf for rf in self.config["risk_factors"]
            if rf.get("market_cap") is not None and rf.get("market_cap", 0) > 0
        ]
        rfs_with_cap.sort(key=lambda x: x["market_cap"], reverse=True)
        return [rf["symbol"] for rf in rfs_with_cap[:n]]

    def create_sector_subset(self, sector: str, output_path: str):
        """Write a JSON subset containing only stocks from ``sector``."""
        sector_rfs = [
            rf for rf in self.config["risk_factors"]
            if rf.get("sector") == sector
        ]

        if not sector_rfs:
            logger.warning(f"No risk factors found for sector '{sector}'")
            return

        sector_config = {
            "group_name": f"sp500_{sector.lower().replace(' ', '_')}",
            "description": f"S&P 500 {sector} sector stocks",
            "asset_class": "equity",
            "asset_subclass": "stock",
            "data_source": self.config["data_source"],
            "frequency": self.config["frequency"],
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "parent_group": self.config["group_name"],
            "sector_filter": sector,
            "risk_factors": sector_rfs,
        }

        subset = RiskFactorGroup(data=sector_config)
        subset.save(path=output_path)
        logger.info(
            f"Created {sector} sector group: {len(sector_rfs)} stocks -> {output_path}"
        )

    def create_market_cap_subset(self, category: str, output_path: str):
        """Write a JSON subset containing only stocks in ``category`` (mega/large/mid/small)."""
        cap_rfs = [
            rf for rf in self.config["risk_factors"]
            if rf.get("market_cap_category") == category
        ]

        if not cap_rfs:
            logger.warning(f"No risk factors found for market cap category '{category}'")
            return

        cap_config = {
            "group_name": f"sp500_{category}_cap",
            "description": f"S&P 500 {category}-cap stocks",
            "asset_class": "equity",
            "asset_subclass": "stock",
            "data_source": self.config["data_source"],
            "frequency": self.config["frequency"],
            "last_updated": datetime.now().strftime("%Y-%m-%d"),
            "parent_group": self.config["group_name"],
            "market_cap_filter": category,
            "risk_factors": cap_rfs,
        }

        subset = RiskFactorGroup(data=cap_config)
        subset.save(path=output_path)
        logger.info(
            f"Created {category}-cap group: {len(cap_rfs)} stocks -> {output_path}"
        )
