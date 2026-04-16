"""
Tests for RiskFactorGroup, the dumb JSON reader/writer at the bottom of
the risk-factor-group hierarchy.

After H4 the constructor accepts either a path or a dict. Production code
that needed the dict path was previously using
`EquityRiskFactorGroup.__new__(...)` to bypass `__init__` — these tests
exist so the proper API is used instead.
"""

import json
from pathlib import Path

import pytest

from finbase.data.risk_factor_groups import RiskFactorGroup


def _sample_config() -> dict:
    return {
        "group_name": "test_group",
        "description": "Test risk factor group",
        "asset_class": "equity",
        "asset_subclass": "stock",
        "data_source": "yfinance",
        "frequency": "daily",
        "last_updated": "2026-04-14",
        "risk_factors": [
            {"symbol": "AAPL", "description": "Apple Inc.", "country": "US"},
            {"symbol": "MSFT", "description": "Microsoft Corp.", "country": "US"},
        ],
    }


class TestRiskFactorGroupFromPath:
    def test_constructor_loads_from_existing_file(self, tmp_path):
        path = tmp_path / "test_group.json"
        path.write_text(json.dumps(_sample_config()))

        group = RiskFactorGroup(group_path=str(path))

        assert group.count() == 2
        assert group.get_symbols() == ["AAPL", "MSFT"]

    def test_constructor_raises_when_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            RiskFactorGroup(group_path=str(tmp_path / "missing.json"))


class TestRiskFactorGroupFromData:
    def test_constructor_accepts_dict_without_file(self):
        group = RiskFactorGroup(data=_sample_config())
        assert group.count() == 2
        assert group.get_metadata()["group_name"] == "test_group"

    def test_save_writes_dict_to_path(self, tmp_path):
        path = tmp_path / "subdir" / "out.json"
        group = RiskFactorGroup(data=_sample_config())

        group.save(path=str(path))

        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["group_name"] == "test_group"
        assert loaded["risk_factors"][0]["symbol"] == "AAPL"

    def test_save_remembers_save_path_for_later(self, tmp_path):
        path = tmp_path / "remembered.json"
        group = RiskFactorGroup(data=_sample_config())

        group.save(path=str(path))
        # Mutate and save without specifying a path
        group.config["risk_factors"].append({"symbol": "GOOGL", "country": "US"})
        group.save()

        loaded = json.loads(path.read_text())
        assert {rf["symbol"] for rf in loaded["risk_factors"]} == {"AAPL", "MSFT", "GOOGL"}

    def test_save_without_path_raises_when_no_path_known(self):
        group = RiskFactorGroup(data=_sample_config())
        with pytest.raises(ValueError, match="path"):
            group.save()


class TestConstructorValidation:
    def test_requires_either_path_or_data(self):
        with pytest.raises(ValueError, match="group_path"):
            RiskFactorGroup()

    def test_rejects_both_path_and_data(self, tmp_path):
        path = tmp_path / "g.json"
        path.write_text(json.dumps(_sample_config()))
        with pytest.raises(ValueError, match="exactly one"):
            RiskFactorGroup(group_path=str(path), data=_sample_config())
