"""
Robustness tests for ``WikipediaIndexParser``:

1. ``symbol_suffix`` — per-index exchange suffix so foreign tickers
   stored in FinBase match YFinance's expectation (``AAL`` → ``AAL.L``
   for FTSE100, preventing silent mis-mapping to American Airlines).

2. ``match_columns`` — structural table identification. Wikipedia's
   fundraising banner periodically injects a <table> at the top of the
   page, shifting every subsequent table index by +1 and silently
   breaking extraction. These tests pin the fallback: when the
   configured ``table_index`` doesn't contain the expected columns,
   scan all tables and use the first that matches.
"""

from typing import Dict, List, Optional
from unittest.mock import patch

import pandas as pd
import pytest

from finbase.data.parsers.wikipedia_index_parser import (
    WikipediaIndexParser,
    WikipediaIndexParserError,
)


def _parser(config: Dict, tables: List[pd.DataFrame]) -> WikipediaIndexParser:
    """Build a parser with canned tables, skipping the network path."""
    parser = WikipediaIndexParser(config)
    parser._tables = tables
    parser._html_content = "<canned>"
    return parser


def _ftse_like_config(
    *,
    symbol_suffix: Optional[str] = None,
    table_index: int = 0,
    match_columns: Optional[List[str]] = None,
    changes_table: Optional[Dict] = None,
) -> Dict:
    constituents = {
        "table_index": table_index,
        "column_mapping": {"Ticker": "symbol", "Company": "company_name"},
    }
    if match_columns is not None:
        constituents["match_columns"] = match_columns
    config = {
        "index_code": "FTSE100",
        "index_name": "FTSE 100",
        "url": "https://example.invalid/ftse",
        "asset_class": "equity",
        "data_source": "wikipedia",
        "constituents_table": constituents,
    }
    if symbol_suffix is not None:
        config["symbol_suffix"] = symbol_suffix
    if changes_table is not None:
        config["changes_table"] = changes_table
    return config


# ---------------------------------------------------------------------------
# symbol_suffix
# ---------------------------------------------------------------------------


class TestSymbolSuffix:
    """Per-exchange suffix handling — the actual fix for the FTSE100 bug."""

    def test_appends_to_bare_symbols(self):
        parser = _parser(
            _ftse_like_config(symbol_suffix=".L"),
            [pd.DataFrame({
                "Ticker": ["AAL", "AZN", "BA"],
                "Company": ["Anglo American", "AstraZeneca", "BAE Systems"],
            })],
        )
        out = parser.get_constituents()
        assert sorted(out["symbol"].tolist()) == ["AAL.L", "AZN.L", "BA.L"]

    def test_idempotent_on_already_suffixed(self):
        """If the Wikipedia scrape already shows ``.L`` (edge case), don't
        double-append."""
        parser = _parser(
            _ftse_like_config(symbol_suffix=".L"),
            [pd.DataFrame({
                "Ticker": ["AAL.L", "AZN"],
                "Company": ["Anglo American", "AstraZeneca"],
            })],
        )
        out = parser.get_constituents()
        assert sorted(out["symbol"].tolist()) == ["AAL.L", "AZN.L"]

    def test_no_suffix_config_leaves_symbols_untouched(self):
        """SP500/NDX/DOW30 configs don't set symbol_suffix; behavior must
        be identical to the pre-suffix implementation."""
        parser = _parser(
            _ftse_like_config(),  # no symbol_suffix
            [pd.DataFrame({
                "Ticker": ["AAPL", "MSFT"],
                "Company": ["Apple", "Microsoft"],
            })],
        )
        out = parser.get_constituents()
        assert sorted(out["symbol"].tolist()) == ["AAPL", "MSFT"]

    def test_suffix_handled_after_strip_and_upper(self):
        """Whitespace and case on raw Wikipedia cells don't confuse the
        suffix logic."""
        parser = _parser(
            _ftse_like_config(symbol_suffix=".L"),
            [pd.DataFrame({
                "Ticker": ["  aal  ", "AZN "],
                "Company": ["Anglo American", "AstraZeneca"],
            })],
        )
        out = parser.get_constituents()
        assert sorted(out["symbol"].tolist()) == ["AAL.L", "AZN.L"]

    def test_empty_suffix_is_noop(self):
        """An empty string suffix should not mutate symbols (defensive)."""
        parser = _parser(
            _ftse_like_config(symbol_suffix=""),
            [pd.DataFrame({
                "Ticker": ["AAPL"],
                "Company": ["Apple"],
            })],
        )
        out = parser.get_constituents()
        assert out["symbol"].tolist() == ["AAPL"]


# ---------------------------------------------------------------------------
# match_columns (banner robustness)
# ---------------------------------------------------------------------------


class TestMatchColumns:
    """Structural table identification as a guard against Wikipedia
    banner-induced table_index drift."""

    def test_uses_table_index_when_expected_columns_present(self):
        """Happy path: configured index points at the right table."""
        parser = _parser(
            _ftse_like_config(table_index=0, match_columns=["Ticker", "Company"]),
            [pd.DataFrame({
                "Ticker": ["AAL"],
                "Company": ["Anglo American"],
            })],
        )
        out = parser.get_constituents()
        assert out["symbol"].tolist() == ["AAL"]

    def test_falls_back_when_banner_shifts_real_table(self):
        """Simulate the classic failure: fundraising banner is now at
        index 0, the constituents table has slid to index 1. Configured
        table_index=0 would silently grab the banner; match_columns
        rescues us."""
        parser = _parser(
            _ftse_like_config(table_index=0, match_columns=["Ticker", "Company"]),
            [
                pd.DataFrame({"Help Wikipedia": ["Donate today"]}),  # banner
                pd.DataFrame({                                       # real
                    "Ticker": ["AAL"],
                    "Company": ["Anglo American"],
                }),
            ],
        )
        out = parser.get_constituents()
        assert out["symbol"].tolist() == ["AAL"]

    def test_without_match_columns_uses_table_index_blindly(self):
        """Backward compat: configs that don't opt into match_columns
        keep the historical positional-index behavior unchanged."""
        parser = _parser(
            _ftse_like_config(table_index=0),  # no match_columns
            [pd.DataFrame({
                "Ticker": ["AAL"],
                "Company": ["Anglo American"],
            })],
        )
        out = parser.get_constituents()
        assert out["symbol"].tolist() == ["AAL"]

    def test_raises_when_no_table_matches(self):
        parser = _parser(
            _ftse_like_config(table_index=0, match_columns=["Nonexistent"]),
            [
                pd.DataFrame({"Foo": [1]}),
                pd.DataFrame({"Bar": [2]}),
            ],
        )
        with pytest.raises(WikipediaIndexParserError, match="No table matches"):
            parser.get_constituents()

    def test_partial_match_not_accepted(self):
        """All listed columns must be present; a partial match falls
        through to the next candidate."""
        parser = _parser(
            _ftse_like_config(table_index=0, match_columns=["Ticker", "Company"]),
            [
                pd.DataFrame({"Ticker": ["AAL"]}),                    # partial
                pd.DataFrame({                                        # full
                    "Ticker": ["AAL"],
                    "Company": ["Anglo American"],
                }),
            ],
        )
        out = parser.get_constituents()
        # Configured table (index 0) has Ticker but no Company → fallback
        assert out["symbol"].tolist() == ["AAL"]
        assert "company_name" in out.columns


class TestMatchColumnsForChanges:
    """Same structural guard for changes tables — they shift too."""

    def test_changes_table_falls_back_on_banner_shift(self):
        changes_cfg = {
            "table_index": 0,
            "match_columns": ["Date", "Added Ticker"],
            "column_mapping": {
                "Date": "date",
                "Added Ticker": "added_ticker",
                "Added Company": "added_company",
            },
        }
        parser = _parser(
            _ftse_like_config(
                table_index=1,
                match_columns=["Ticker"],
                changes_table=changes_cfg,
            ),
            [
                pd.DataFrame({"Donate": ["Yes"]}),                    # banner
                pd.DataFrame({"Ticker": ["AAL"]}),                    # constituents
                pd.DataFrame({                                        # changes
                    "Date": ["2025-01-01"],
                    "Added Ticker": ["NEW"],
                    "Added Company": ["New Co"],
                }),
            ],
        )
        changes = parser.get_changes()
        assert changes is not None
        assert changes["added_ticker"].tolist() == ["NEW"]


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------


class TestMatchColumnsAndSuffixCompose:
    def test_banner_shift_and_suffix_apply_together(self):
        parser = _parser(
            _ftse_like_config(
                symbol_suffix=".L",
                table_index=0,
                match_columns=["Ticker"],
            ),
            [
                pd.DataFrame({"Banner": ["Donate"]}),
                pd.DataFrame({
                    "Ticker": ["AAL", "AZN"],
                    "Company": ["Anglo", "AstraZeneca"],
                }),
            ],
        )
        out = parser.get_constituents()
        assert sorted(out["symbol"].tolist()) == ["AAL.L", "AZN.L"]


# ---------------------------------------------------------------------------
# Real FTSE100 config should ship with both fields set
# ---------------------------------------------------------------------------


class TestFTSE100ConfigOnDisk:
    """Guard against regressions in the shipped ftse100.json."""

    def test_ftse100_config_has_symbol_suffix_L(self):
        parser = WikipediaIndexParser.from_index_code("FTSE100")
        assert parser.config.get("symbol_suffix") == ".L", (
            "FTSE100 config must set symbol_suffix='.L' so Wikipedia's "
            "bare tickers are stored + queried against LSE, not US."
        )

    def test_ftse100_constituents_table_has_match_columns(self):
        parser = WikipediaIndexParser.from_index_code("FTSE100")
        ct = parser.config["constituents_table"]
        assert ct.get("match_columns"), (
            "FTSE100 constituents_table must set match_columns to survive "
            "Wikipedia banner shifts."
        )
