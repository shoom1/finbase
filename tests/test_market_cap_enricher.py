"""
Tests for MarketCapEnricher — the YFinance-facing helper that decorates a
RiskFactorGroup with market_cap and market_cap_category fields.

This logic used to live on EquityRiskFactorGroup as `update_market_caps()`,
mixing JSON I/O with network calls in the same class. H4 splits it into a
dedicated service that takes a group and a `ticker_factory` (so tests can
inject fakes without monkeypatching the yfinance module).
"""

from typing import Dict
from unittest.mock import patch

import pytest

from finbase.data.risk_factor_groups import RiskFactorGroup
from finbase.data.risk_factor_groups.market_cap_enricher import (
    MarketCapEnricher,
    categorize_market_cap,
)


def _make_group() -> RiskFactorGroup:
    return RiskFactorGroup(
        data={
            "group_name": "tiny_test",
            "asset_class": "equity",
            "data_source": "yfinance",
            "frequency": "daily",
            "risk_factors": [
                {"symbol": "MEGA", "country": "US"},
                {"symbol": "LARGE", "country": "US"},
                {"symbol": "MID", "country": "US"},
                {"symbol": "SMALL", "country": "US"},
                {"symbol": "FAILS", "country": "US"},
            ],
        }
    )


class FakeTicker:
    def __init__(self, market_cap):
        self._info = {"marketCap": market_cap}

    @property
    def info(self) -> Dict:
        return self._info


def fake_ticker_factory(symbol: str) -> FakeTicker:
    return {
        "MEGA": FakeTicker(500_000_000_000),
        "LARGE": FakeTicker(50_000_000_000),
        "MID": FakeTicker(5_000_000_000),
        "SMALL": FakeTicker(500_000_000),
        "FAILS": FakeTicker(0),
    }[symbol]


class TestCategorizeMarketCap:
    @pytest.mark.parametrize(
        "cap, category",
        [
            (500_000_000_000, "mega"),
            (200_000_000_001, "mega"),
            (200_000_000_000, "large"),
            (50_000_000_000, "large"),
            (10_000_000_001, "large"),
            (10_000_000_000, "mid"),
            (5_000_000_000, "mid"),
            (2_000_000_001, "mid"),
            (2_000_000_000, "small"),
            (500_000_000, "small"),
            (0, "small"),
        ],
    )
    def test_thresholds(self, cap, category):
        assert categorize_market_cap(cap) == category


class TestMarketCapEnricher:
    def test_enrich_decorates_each_risk_factor(self):
        group = _make_group()
        enricher = MarketCapEnricher(ticker_factory=fake_ticker_factory)

        updated = enricher.enrich(group)

        # Each risk factor now carries market_cap + category
        for rf in group.config["risk_factors"]:
            assert "market_cap" in rf
            assert "market_cap_category" in rf

        # Sanity: categories follow our thresholds
        by_symbol = {rf["symbol"]: rf for rf in group.config["risk_factors"]}
        assert by_symbol["MEGA"]["market_cap_category"] == "mega"
        assert by_symbol["LARGE"]["market_cap_category"] == "large"
        assert by_symbol["MID"]["market_cap_category"] == "mid"
        assert by_symbol["SMALL"]["market_cap_category"] == "small"

        assert updated == 5

    def test_enrich_handles_ticker_errors_gracefully(self):
        def factory(symbol):
            if symbol == "FAILS":
                raise RuntimeError("ticker fetch failed")
            return fake_ticker_factory(symbol)

        group = _make_group()
        enricher = MarketCapEnricher(ticker_factory=factory)

        updated = enricher.enrich(group)

        by_symbol = {rf["symbol"]: rf for rf in group.config["risk_factors"]}
        assert by_symbol["FAILS"]["market_cap"] is None
        assert by_symbol["FAILS"]["market_cap_category"] == "unknown"
        assert updated == 4  # 4 successful, 1 failed

    def test_enrich_persists_via_save_callback(self, tmp_path):
        group = RiskFactorGroup(
            data={
                "group_name": "persist_test",
                "asset_class": "equity",
                "data_source": "yfinance",
                "frequency": "daily",
                "risk_factors": [{"symbol": "MEGA", "country": "US"}],
            }
        )
        path = tmp_path / "g.json"
        group.save(path=str(path))

        enricher = MarketCapEnricher(ticker_factory=fake_ticker_factory)
        enricher.enrich(group, save_every=1)

        # File on disk now reflects the enriched factors
        import json

        loaded = json.loads(path.read_text())
        assert loaded["risk_factors"][0]["market_cap"] == 500_000_000_000


class TestDefaultTickerFactory:
    """The default factory just delegates to yfinance.Ticker."""

    def test_default_factory_uses_yfinance(self):
        with patch(
            "finbase.data.risk_factor_groups.market_cap_enricher.yf"
        ) as mock_yf:
            enricher = MarketCapEnricher()
            enricher._ticker_factory("AAPL")
            mock_yf.Ticker.assert_called_once_with("AAPL")
