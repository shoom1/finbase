"""
Wire-up tests proving EquityLoader honors `Settings.rate_limit` instead of
relying on caller-provided constants.

Before this fix, `EquityLoader.__init__` had hardcoded default arguments
(`delay_seconds=5.0`, `batch_size=10`, `batch_pause=30.0`) and the
`Settings.rate_limit` object — and its `FINBASE_YFINANCE_*` env-var
overrides — were dead code: nothing in the loading pipeline read them.
These tests would have caught that.
"""

import os
from unittest.mock import patch

import pytest

from finbase.config import get_settings
from finbase.data.loaders.equity_loader import EquityLoader


@pytest.fixture(autouse=True)
def _reset_settings_cache(monkeypatch, tmp_path):
    """Reset the cached global settings before and after each test.

    Also redirects HOME to a temp directory so the dev's real
    ``~/.finbaserc`` can't bleed its ``rate_limit`` values (or any future
    fields) into these assertions.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    get_settings(reload=True)
    yield
    # Clean up any env-var pollution and rehydrate cache
    for key in (
        "FINBASE_YFINANCE_DELAY",
        "FINBASE_YFINANCE_BATCH_SIZE",
        "FINBASE_YFINANCE_BATCH_PAUSE",
    ):
        os.environ.pop(key, None)
    get_settings(reload=True)


class TestEquityLoaderUsesSettings:
    """Constructing without args must read from Settings.rate_limit."""

    def test_no_args_uses_settings_defaults(self, test_db):
        settings = get_settings()
        loader = EquityLoader(test_db)
        assert loader.delay_seconds == settings.rate_limit.yfinance_delay_seconds
        assert loader.batch_size == settings.rate_limit.yfinance_batch_size
        assert loader.batch_pause == settings.rate_limit.yfinance_batch_pause

    def test_explicit_args_still_win(self, test_db):
        loader = EquityLoader(
            test_db, delay_seconds=0.1, batch_size=3, batch_pause=0.2
        )
        assert loader.delay_seconds == 0.1
        assert loader.batch_size == 3
        assert loader.batch_pause == 0.2


class TestEquityLoaderRespectsEnvOverrides:
    """Env-var overrides must reach the loader through Settings."""

    def test_env_overrides_delay(self, test_db):
        with patch.dict(os.environ, {"FINBASE_YFINANCE_DELAY": "0.25"}, clear=False):
            get_settings(reload=True)
            loader = EquityLoader(test_db)
            assert loader.delay_seconds == 0.25

    def test_env_overrides_batch_size(self, test_db):
        with patch.dict(os.environ, {"FINBASE_YFINANCE_BATCH_SIZE": "7"}, clear=False):
            get_settings(reload=True)
            loader = EquityLoader(test_db)
            assert loader.batch_size == 7

    def test_env_overrides_batch_pause(self, test_db):
        with patch.dict(os.environ, {"FINBASE_YFINANCE_BATCH_PAUSE": "1.5"}, clear=False):
            get_settings(reload=True)
            loader = EquityLoader(test_db)
            assert loader.batch_pause == 1.5
