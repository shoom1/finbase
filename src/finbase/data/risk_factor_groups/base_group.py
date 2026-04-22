"""Base class for managing risk factor group definitions from JSON files."""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class RiskFactorGroup:
    """Plain JSON reader/writer for risk-factor group configs.

    Construct from either an existing path (``group_path``) or an
    in-memory dict (``data``). Exactly one must be provided. The dict
    form is what the bootstrapping flows in ``setup_database.py`` use
    when seeding a new group from Wikipedia — previously they bypassed
    ``__init__`` with ``__new__``, which this constructor replaces.
    """

    def __init__(
        self,
        group_path: Optional[str] = None,
        data: Optional[Dict] = None,
    ):
        if group_path is None and data is None:
            raise ValueError(
                "RiskFactorGroup requires either a group_path or a data dict"
            )
        if group_path is not None and data is not None:
            raise ValueError(
                "RiskFactorGroup accepts exactly one of group_path or data, not both"
            )

        if group_path is not None:
            self.group_path: Optional[Path] = Path(group_path)
            self.config: Dict = self._load_from_path(self.group_path)
        else:
            self.group_path = None
            self.config = data  # type: ignore[assignment]

    @staticmethod
    def _load_from_path(path: Path) -> Dict:
        if not path.exists():
            raise FileNotFoundError(f"Risk factor group file not found: {path}")
        with open(path, "r") as f:
            return json.load(f)

    def load(self) -> Dict:
        """Reload from `self.group_path` if one is known."""
        if self.group_path is None:
            raise ValueError("Cannot load: this group was constructed from a dict")
        self.config = self._load_from_path(self.group_path)
        return self.config

    def save(self, path: Optional[str] = None):
        """Persist the current config to JSON.

        Pass an explicit ``path`` the first time when the group was
        constructed from a dict; subsequent saves remember it.
        """
        if path is not None:
            self.group_path = Path(path)
        if self.group_path is None:
            raise ValueError(
                "save() requires a path the first time when the group was "
                "constructed from a dict"
            )

        self.config["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        self.group_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.group_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_symbols(self) -> List[str]:
        """Return list of symbols in this group."""
        return [rf["symbol"] for rf in self.config["risk_factors"]]

    def get_metadata(self) -> Dict:
        """Return group metadata (asset_class, data_source, etc.)."""
        return {
            "group_name": self.config["group_name"],
            "description": self.config.get("description", ""),
            "asset_class": self.config["asset_class"],
            "asset_subclass": self.config.get("asset_subclass"),
            "data_source": self.config["data_source"],
            "frequency": self.config["frequency"],
            "last_updated": self.config.get("last_updated"),
        }

    def get_risk_factor(self, symbol: str) -> Optional[Dict]:
        """Get full details for a specific risk factor, or ``None``."""
        for rf in self.config["risk_factors"]:
            if rf["symbol"] == symbol:
                return rf
        return None

    def filter_by(self, **kwargs) -> List[str]:
        """Filter risk factors by attributes.

        Examples:
            filter_by(sector='Technology')
            filter_by(country='US', market_cap_category='mega')
        """
        filtered = []
        for rf in self.config["risk_factors"]:
            if all(rf.get(key) == value for key, value in kwargs.items()):
                filtered.append(rf["symbol"])
        return filtered

    def count(self) -> int:
        """Return number of risk factors in this group."""
        return len(self.config["risk_factors"])

    def __repr__(self) -> str:
        meta = self.get_metadata()
        return (
            f"RiskFactorGroup('{meta['group_name']}', "
            f"{self.count()} factors, {meta['asset_class']})"
        )

    def __len__(self) -> int:
        return self.count()
