"""
Tests for WikipediaIndexParser.

The bulk of the parser's behavior was historically only exercised through
SP500WikipediaParser (the legacy specialized variant). H3 lifts the
export/summary helpers up here so every index gets them, and pins them with
direct tests against the generic parser.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, Mock

import pandas as pd
import pytest

from finbase.data.parsers.wikipedia_index_parser import (
    WikipediaIndexParser,
    WikipediaIndexParserError,
)


SP500_HTML = """
<html>
<body>
    <table>
        <tr>
            <th>Symbol</th>
            <th>Security</th>
            <th>GICS Sector</th>
            <th>GICS Sub-Industry</th>
            <th>Headquarters Location</th>
            <th>Date added</th>
            <th>CIK</th>
            <th>Founded</th>
        </tr>
        <tr>
            <td>AAPL</td>
            <td>Apple Inc.</td>
            <td>Information Technology</td>
            <td>Technology Hardware, Storage &amp; Peripherals</td>
            <td>Cupertino, California</td>
            <td>1982-11-30</td>
            <td>320193</td>
            <td>1976</td>
        </tr>
        <tr>
            <td>MSFT</td>
            <td>Microsoft Corporation</td>
            <td>Information Technology</td>
            <td>Systems Software</td>
            <td>Redmond, Washington</td>
            <td>1994-06-01</td>
            <td>789019</td>
            <td>1975</td>
        </tr>
    </table>
    <table>
        <tr>
            <th>Date</th>
            <th>Added Ticker</th>
            <th>Added Security</th>
            <th>Removed Ticker</th>
            <th>Removed Security</th>
            <th>Reason</th>
        </tr>
        <tr>
            <td>2024-12-01</td>
            <td>NEW</td>
            <td>New Company</td>
            <td>OLD</td>
            <td>Old Company</td>
            <td>Market cap change</td>
        </tr>
    </table>
</body>
</html>
"""


def _patched_parser(html: str = SP500_HTML) -> WikipediaIndexParser:
    """Build an SP500 parser whose `requests.get` returns canned HTML."""
    parser = WikipediaIndexParser.from_index_code("SP500")
    mock_response = Mock()
    mock_response.text = html
    mock_response.raise_for_status = Mock()

    patcher = patch(
        "finbase.data.parsers.wikipedia_index_parser.requests.get",
        return_value=mock_response,
    )
    patcher.start()
    parser._patcher = patcher  # so the test can stop it in teardown
    return parser


@pytest.fixture
def sp500_parser():
    parser = _patched_parser()
    yield parser
    parser._patcher.stop()


class TestExportToCSV:
    def test_export_writes_constituents_and_changes_files(self, sp500_parser, tmp_path):
        files = sp500_parser.export_to_csv(output_dir=str(tmp_path))
        assert "constituents" in files
        assert "changes" in files
        assert Path(files["constituents"]).exists()
        assert Path(files["changes"]).exists()
        # Verify roundtrip
        constituents = pd.read_csv(files["constituents"])
        assert "symbol" in constituents.columns
        assert len(constituents) > 0

    def test_export_uses_index_code_as_default_prefix(self, sp500_parser, tmp_path):
        files = sp500_parser.export_to_csv(output_dir=str(tmp_path))
        assert "sp500_constituents_" in files["constituents"]

    def test_export_accepts_explicit_prefix(self, sp500_parser, tmp_path):
        files = sp500_parser.export_to_csv(output_dir=str(tmp_path), prefix="my_prefix")
        assert "my_prefix_constituents_" in files["constituents"]

    def test_export_skips_changes_when_unavailable(self, sp500_parser, tmp_path):
        # Force get_changes to return None (e.g., index without changes_table)
        with patch.object(sp500_parser, "get_changes", return_value=None):
            files = sp500_parser.export_to_csv(output_dir=str(tmp_path))
            assert files.get("changes") is None
            assert Path(files["constituents"]).exists()


class TestExportToJSON:
    def test_export_writes_json_files(self, sp500_parser, tmp_path):
        files = sp500_parser.export_to_json(output_dir=str(tmp_path))
        assert Path(files["constituents"]).exists()
        # File parses as JSON
        with open(files["constituents"]) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0


class TestGetSummaryStats:
    def test_summary_includes_total_constituents_and_sectors(self, sp500_parser):
        stats = sp500_parser.get_summary_stats()
        assert "total_constituents" in stats
        assert "sectors" in stats
        assert stats["total_constituents"] > 0
        assert isinstance(stats["sectors"], dict)

    def test_summary_includes_changes_metadata(self, sp500_parser):
        stats = sp500_parser.get_summary_stats()
        assert "total_changes" in stats
        assert "data_date" in stats
        assert stats["total_changes"] >= 0

    def test_summary_includes_index_metadata(self, sp500_parser):
        stats = sp500_parser.get_summary_stats()
        assert stats.get("index_code") == "SP500"
        assert "index_name" in stats
