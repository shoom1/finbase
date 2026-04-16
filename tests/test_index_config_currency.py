"""
Tests pinning currency/country resolution to index config files instead of
the historical hardcoded maps in `scripts/setup_database.py`.

Adding a new index used to require touching:
  - data/index_configs/<code>.json   (config)
  - scripts/setup_database.py        (country_map + currency_map)
  - CLAUDE.md                        (docs)

After this fix, the JSON config is the single source of truth, and the
loader script reads `country` and `currency` straight off the parser.
"""

import json
from importlib.resources import files

import pytest

from finbase.data.parsers.wikipedia_index_parser import WikipediaIndexParser


CONFIG_DIR = files("finbase.index_configs")
ALL_INDEX_CODES = ["SP500", "DOW30", "NDX", "FTSE100", "DAX"]
EXPECTED_CURRENCIES = {
    "SP500": "USD",
    "DOW30": "USD",
    "NDX": "USD",
    "FTSE100": "GBP",
    "DAX": "EUR",
}
EXPECTED_COUNTRIES = {
    "SP500": "US",
    "DOW30": "US",
    "NDX": "US",
    "FTSE100": "GB",
    "DAX": "DE",
}


@pytest.mark.parametrize("index_code", ALL_INDEX_CODES)
def test_index_config_declares_currency(index_code: str):
    """Each shipped index config must include a `currency` field."""
    config_text = (CONFIG_DIR / f"{index_code.lower()}.json").read_text(encoding="utf-8")
    config = json.loads(config_text)
    assert "currency" in config, f"{index_code} config is missing the currency field"
    assert config["currency"] == EXPECTED_CURRENCIES[index_code]


@pytest.mark.parametrize("index_code", ALL_INDEX_CODES)
def test_index_config_declares_country(index_code: str):
    """Sanity: country was already there but we want a regression guard."""
    config_text = (CONFIG_DIR / f"{index_code.lower()}.json").read_text(encoding="utf-8")
    config = json.loads(config_text)
    assert config.get("country") == EXPECTED_COUNTRIES[index_code]


@pytest.mark.parametrize("index_code", ALL_INDEX_CODES)
def test_parser_exposes_currency_and_country(index_code: str):
    """`WikipediaIndexParser.from_index_code` must surface both fields."""
    parser = WikipediaIndexParser.from_index_code(index_code)
    assert parser.config.get("currency") == EXPECTED_CURRENCIES[index_code]
    assert parser.config.get("country") == EXPECTED_COUNTRIES[index_code]


def test_setup_database_has_no_country_or_currency_map():
    """
    The hardcoded `country_map` / `currency_map` in setup_database.py must
    be gone — they were the duplication this fix exists to remove.
    """
    script_path = (
        files("finbase").joinpath("..", "..", "scripts", "setup_database.py")
    )
    # Resolve via repo root because importlib joins don't traverse outside packages.
    from pathlib import Path

    repo_script = Path(__file__).resolve().parent.parent / "scripts" / "setup_database.py"
    text = repo_script.read_text(encoding="utf-8")
    assert "country_map" not in text, (
        "setup_database.py still defines a hardcoded country_map; "
        "country must come from the index config JSON"
    )
    assert "currency_map" not in text, (
        "setup_database.py still defines a hardcoded currency_map; "
        "currency must come from the index config JSON"
    )
