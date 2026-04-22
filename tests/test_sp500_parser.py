"""
Tests for S&P 500 Wikipedia parser.

The class is now a deprecated wrapper around `WikipediaIndexParser`. These
tests pin the back-compat surface so future migrations don't silently
break callers that still import `SP500WikipediaParser`.
"""

import warnings
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch
import sys
from pathlib import Path

from finbase.data.parsers.sp500_wikipedia import SP500WikipediaParser, SP500ParserError

# These tests intentionally instantiate the deprecated class — silence the
# warnings so the suite output stays focused on real failures.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


class TestSP500WikipediaParser:
    """Test suite for SP500WikipediaParser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return SP500WikipediaParser()

    @pytest.fixture
    def mock_html(self):
        """Mock HTML content with S&P 500 tables."""
        return """
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

    def test_parser_initialization(self, parser):
        """Test parser initialization."""
        assert parser.url == SP500WikipediaParser.WIKIPEDIA_URL
        assert parser._html_content is None
        assert parser._tables is None

    def test_parser_custom_url(self):
        """Test parser with custom URL."""
        custom_url = "https://example.com/custom"
        parser = SP500WikipediaParser(url=custom_url)
        assert parser.url == custom_url

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_fetch_page_success(self, mock_get, parser, mock_html):
        """Test successful page fetch."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        content = parser.fetch_page()

        assert content == mock_html
        assert parser._html_content == mock_html
        mock_get.assert_called_once()

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_fetch_page_failure(self, mock_get, parser):
        """Test page fetch failure."""
        import requests as _requests

        mock_get.side_effect = _requests.RequestException("Network error")

        with pytest.raises(SP500ParserError, match="Failed to fetch Wikipedia page"):
            parser.fetch_page()

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_get_current_constituents(self, mock_get, parser, mock_html):
        """Test extracting current constituents."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        constituents = parser.get_current_constituents()

        # Check it's a DataFrame
        assert isinstance(constituents, pd.DataFrame)

        # Check it has data
        assert len(constituents) > 0

        # Check expected columns exist (after renaming)
        assert 'symbol' in constituents.columns
        assert 'company_name' in constituents.columns
        assert 'sector' in constituents.columns

        # Check symbols are uppercase and stripped
        assert all(constituents['symbol'].str.isupper())

        # Check metadata columns
        assert 'extracted_at' in constituents.columns
        assert 'source' in constituents.columns
        assert all(constituents['source'] == 'wikipedia')

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_get_historical_changes(self, mock_get, parser, mock_html):
        """Test extracting historical changes."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        changes = parser.get_historical_changes()

        # Check it's a DataFrame
        assert isinstance(changes, pd.DataFrame)

        # Should have data
        assert len(changes) > 0

        # Check metadata columns
        assert 'extracted_at' in changes.columns
        assert 'source' in changes.columns
        assert all(changes['source'] == 'wikipedia')

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_get_all_data(self, mock_get, parser, mock_html):
        """Test getting both constituents and changes."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        constituents, changes = parser.get_all_data()

        # Both should be DataFrames
        assert isinstance(constituents, pd.DataFrame)
        assert isinstance(changes, pd.DataFrame)

        # Both should have data
        assert len(constituents) > 0
        assert len(changes) > 0

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_export_to_csv(self, mock_get, parser, mock_html, tmp_path):
        """Test CSV export."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        output_dir = str(tmp_path)
        files = parser.export_to_csv(output_dir=output_dir, prefix="test")

        # Check both files created
        assert 'constituents' in files
        assert 'changes' in files

        # Check files exist
        assert Path(files['constituents']).exists()
        assert Path(files['changes']).exists()

        # Verify can read back
        constituents_read = pd.read_csv(files['constituents'])
        changes_read = pd.read_csv(files['changes'])

        assert len(constituents_read) > 0
        assert len(changes_read) > 0

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_export_to_json(self, mock_get, parser, mock_html, tmp_path):
        """Test JSON export."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        output_dir = str(tmp_path)
        files = parser.export_to_json(output_dir=output_dir, prefix="test")

        # Check both files created
        assert 'constituents' in files
        assert 'changes' in files

        # Check files exist
        assert Path(files['constituents']).exists()
        assert Path(files['changes']).exists()

        # Verify can read back
        constituents_read = pd.read_json(files['constituents'])
        changes_read = pd.read_json(files['changes'])

        assert len(constituents_read) > 0
        assert len(changes_read) > 0

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_get_summary_stats(self, mock_get, parser, mock_html):
        """Test summary statistics."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        stats = parser.get_summary_stats()

        # Check expected keys
        assert 'total_constituents' in stats
        assert 'sectors' in stats
        assert 'total_changes' in stats
        assert 'recent_additions' in stats
        assert 'recent_removals' in stats
        assert 'data_date' in stats

        # Check values
        assert stats['total_constituents'] > 0
        assert stats['total_changes'] >= 0
        assert isinstance(stats['sectors'], dict)

    def test_empty_tables(self, parser):
        """Test handling of empty/missing tables."""
        # Set HTML with no tables
        parser._html_content = "<html><body>No tables here</body></html>"

        # Should raise error or return empty DataFrame
        with pytest.raises(SP500ParserError):
            parser._parse_tables()

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_date_parsing(self, mock_get, parser, mock_html):
        """Test that dates are parsed correctly."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        constituents = parser.get_current_constituents()

        if 'date_added' in constituents.columns:
            # Check dates are datetime type
            assert pd.api.types.is_datetime64_any_dtype(constituents['date_added'])

    @patch('finbase.data.parsers.wikipedia_index_parser.requests.get')
    def test_symbol_cleaning(self, mock_get, parser, mock_html):
        """Test that symbols are cleaned (uppercase, trimmed)."""
        mock_response = Mock()
        mock_response.text = mock_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        constituents = parser.get_current_constituents()

        if 'symbol' in constituents.columns:
            # All symbols should be uppercase
            assert all(constituents['symbol'] == constituents['symbol'].str.upper())
            # No leading/trailing whitespace
            assert all(constituents['symbol'] == constituents['symbol'].str.strip())


# Integration test (requires internet connection)
@pytest.mark.integration
class TestSP500WikipediaParserIntegration:
    """Integration tests that fetch real data from Wikipedia."""

    def test_fetch_real_data(self):
        """Test fetching real S&P 500 data from Wikipedia."""
        parser = SP500WikipediaParser()

        # Fetch current constituents
        constituents = parser.get_current_constituents()

        # Should have ~500 companies
        assert 400 <= len(constituents) <= 600, f"Expected ~500 constituents, got {len(constituents)}"

        # Check expected columns
        assert 'symbol' in constituents.columns
        assert 'company_name' in constituents.columns
        assert 'sector' in constituents.columns

        # Check some well-known companies
        symbols = constituents['symbol'].tolist()
        assert 'AAPL' in symbols, "Apple should be in S&P 500"
        assert 'MSFT' in symbols, "Microsoft should be in S&P 500"
        assert 'GOOGL' in symbols or 'GOOG' in symbols, "Google should be in S&P 500"

    def test_fetch_real_changes(self):
        """Test fetching real historical changes."""
        parser = SP500WikipediaParser()

        changes = parser.get_historical_changes()

        # Should have some changes
        assert len(changes) > 0, "Should have historical changes"

        # Check columns exist
        assert 'date' in changes.columns


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
