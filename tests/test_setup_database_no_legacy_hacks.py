"""
Static guards against H4 regressions in scripts/setup_database.py.

The old `setup_sp500_group` reached for `EquityRiskFactorGroup.__new__` to
bypass `__init__`, and `equity_group.py` carried an
`update_from_wikipedia_sp500` method that duplicated WikipediaIndexParser.
Both are now considered code smells; these tests fail the build if they
sneak back in.
"""

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "setup_database.py"
EQUITY_GROUP = (
    REPO_ROOT / "src" / "finbase" / "data" / "risk_factor_groups" / "equity_group.py"
)


def test_setup_database_does_not_use_new_hack():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "EquityRiskFactorGroup.__new__" not in text, (
        "setup_database.py still bypasses __init__ with __new__; "
        "use RiskFactorGroup(data=...) instead"
    )


def test_equity_group_no_longer_scrapes_wikipedia():
    text = EQUITY_GROUP.read_text(encoding="utf-8")
    # Only flag if there's an actual `def update_from_wikipedia_sp500`;
    # historical references in docstrings are fine and informative.
    assert "def update_from_wikipedia_sp500" not in text, (
        "EquityRiskFactorGroup must not re-implement Wikipedia scraping; "
        "use WikipediaIndexParser.from_index_code('SP500') instead"
    )


def test_equity_group_no_longer_imports_pd_read_html():
    text = EQUITY_GROUP.read_text(encoding="utf-8")
    assert "pd.read_html" not in text, (
        "Wikipedia HTML parsing must live in WikipediaIndexParser, "
        "not in equity_group.py"
    )


def test_setup_database_still_creates_sp500_group():
    """Sanity: the function exists, just refactored."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "def setup_sp500_group" in text


def test_equity_group_no_longer_owns_market_cap_enrichment():
    text = EQUITY_GROUP.read_text(encoding="utf-8")
    assert "import yfinance" not in text, (
        "YFinance imports belong in MarketCapEnricher, not equity_group.py"
    )
    assert "def update_market_caps" not in text, (
        "Market-cap enrichment lives in MarketCapEnricher now"
    )
