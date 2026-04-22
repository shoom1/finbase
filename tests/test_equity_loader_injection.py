"""
Guards EquityLoader's ticker-factory DI, matching the pattern that
MarketCapEnricher already uses.

Before this fix, ``yfinance`` was imported at the top of
``equity_loader.py`` and called directly via ``yf.Ticker(symbol)``. Tests
had to monkeypatch the module-level ``yf`` to avoid real network calls.
These tests pin the contract: a ``ticker_factory`` kwarg lets callers
hand in a custom factory (fake, stub, or alt-source) with no yfinance
awareness required.
"""

import pandas as pd
import pytest

from finbase.data.loaders.equity_loader import EquityLoader


class _FakeTicker:
    """Quacks like ``yf.Ticker`` as far as EquityLoader cares."""

    def __init__(self, df: pd.DataFrame):
        self._df = df

    def history(self, start: str, end: str, auto_adjust: bool = False) -> pd.DataFrame:
        return self._df


def _make_yf_like_df(periods: int = 3) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=periods, freq="B")
    return pd.DataFrame(
        {
            "Open": [150.0 + i for i in range(periods)],
            "High": [155.0 + i for i in range(periods)],
            "Low": [149.0 + i for i in range(periods)],
            "Close": [153.0 + i for i in range(periods)],
            "Adj Close": [152.0 + i for i in range(periods)],
            "Volume": [1_000_000 + i * 10_000 for i in range(periods)],
        },
        index=dates,
    )


class TestTickerFactoryInjection:
    """Caller-supplied factories must replace the yfinance default."""

    def test_factory_is_called_instead_of_yfinance(self, test_db):
        calls = []

        def fake_factory(symbol: str):
            calls.append(symbol)
            return _FakeTicker(_make_yf_like_df(3))

        loader = EquityLoader(
            test_db,
            delay_seconds=0,
            batch_size=100,
            batch_pause=0,
            ticker_factory=fake_factory,
        )
        records = loader.load_symbol("AAPL", "2024-01-01", "2024-01-31")

        assert calls == ["AAPL"]
        assert records == 3

    def test_network_never_hit_when_factory_provided(self, test_db, monkeypatch):
        """If the factory short-circuits, yfinance.Ticker must not be touched."""
        sentinel = object()

        def explode(*args, **kwargs):
            raise AssertionError("yfinance.Ticker was called despite custom factory")

        monkeypatch.setattr("finbase.data.loaders.equity_loader.yf.Ticker", explode)

        def stub_factory(symbol: str):
            return _FakeTicker(_make_yf_like_df(2))

        loader = EquityLoader(
            test_db,
            delay_seconds=0,
            batch_size=100,
            batch_pause=0,
            ticker_factory=stub_factory,
        )
        loader.load_symbol("MSFT", "2024-01-01", "2024-01-31")

    def test_default_factory_still_uses_yfinance(self, test_db, monkeypatch):
        """No ``ticker_factory`` argument → must fall back to yfinance."""
        seen = []

        class _StubYf:
            @staticmethod
            def Ticker(symbol):
                seen.append(symbol)
                return _FakeTicker(_make_yf_like_df(1))

        monkeypatch.setattr("finbase.data.loaders.equity_loader.yf", _StubYf)

        loader = EquityLoader(test_db, delay_seconds=0, batch_size=100, batch_pause=0)
        loader.load_symbol("GOOGL", "2024-01-01", "2024-01-31")

        assert seen == ["GOOGL"]

    def test_factory_receives_exact_symbol_string(self, test_db):
        """Symbol is passed to the factory unmodified."""
        received = []

        def factory(symbol: str):
            received.append(symbol)
            return _FakeTicker(_make_yf_like_df(1))

        loader = EquityLoader(
            test_db,
            delay_seconds=0,
            batch_size=100,
            batch_pause=0,
            ticker_factory=factory,
        )
        loader.load_symbol("BRK-B", "2024-01-01", "2024-01-31")

        assert received == ["BRK-B"]
