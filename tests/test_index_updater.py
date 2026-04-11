"""Tests for IndexUpdater - orchestrates index updates."""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import datetime, date

from finbase.data.index_updater import IndexUpdater, IndexUpdaterError
from finbase.data.database.index_db import IndexDB


class TestUpdateFromWikipedia:

    def _make_mock_constituents(self):
        return pd.DataFrame({
            'symbol': ['AAPL', 'MSFT', 'GOOGL'],
            'company_name': ['Apple', 'Microsoft', 'Alphabet'],
            'sector': ['Technology', 'Technology', 'Communication Services'],
            'source': ['wikipedia'] * 3,
        })

    def _make_mock_config(self):
        return {
            'index_code': 'SP500',
            'index_name': 'S&P 500',
            'description': 'Test',
            'country': 'US',
            'data_source': 'wikipedia',
            'asset_class': 'equity',
            'url': 'https://en.wikipedia.org/wiki/Test',
        }

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_update_registers_index_and_adds_constituents(self, mock_parser_cls, index_db):
        mock_parser = MagicMock()
        mock_parser.config = self._make_mock_config()
        mock_parser.get_constituents.return_value = self._make_mock_constituents()
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)
        summary = updater.update_from_wikipedia('SP500')

        assert summary['index_code'] == 'SP500'
        assert summary['total_constituents'] == 3
        assert summary['added_count'] == 3
        assert summary['removed_count'] == 0

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_update_detects_changes_on_second_run(self, mock_parser_cls, index_db):
        mock_parser = MagicMock()
        mock_parser.config = self._make_mock_config()
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)

        # First run: load 3 symbols
        mock_parser.get_constituents.return_value = self._make_mock_constituents()
        updater.update_from_wikipedia('SP500')

        # Second run: remove GOOGL, add NVDA
        mock_parser.get_constituents.return_value = pd.DataFrame({
            'symbol': ['AAPL', 'MSFT', 'NVDA'],
            'company_name': ['Apple', 'Microsoft', 'NVIDIA'],
            'sector': ['Technology', 'Technology', 'Technology'],
            'source': ['wikipedia'] * 3,
        })
        summary = updater.update_from_wikipedia('SP500')
        assert summary['added_count'] == 1
        assert summary['removed_count'] == 1

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_update_parser_failure_raises(self, mock_parser_cls, index_db):
        from finbase.data.parsers.wikipedia_index_parser import WikipediaIndexParserError
        mock_parser_cls.from_index_code.side_effect = WikipediaIndexParserError("not found")

        updater = IndexUpdater(index_db)
        with pytest.raises(IndexUpdaterError, match="Failed to load parser"):
            updater.update_from_wikipedia('FAKE')

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_summary_contains_expected_keys(self, mock_parser_cls, index_db):
        mock_parser = MagicMock()
        mock_parser.config = self._make_mock_config()
        mock_parser.get_constituents.return_value = self._make_mock_constituents()
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)
        summary = updater.update_from_wikipedia('SP500')

        expected_keys = {
            'index_code', 'index_name', 'total_constituents',
            'added_count', 'removed_count', 'unchanged_count',
            'added_symbols', 'removed_symbols', 'extraction_time', 'data_source'
        }
        assert expected_keys.issubset(summary.keys())

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_update_no_changes_on_identical_second_run(self, mock_parser_cls, index_db):
        mock_parser = MagicMock()
        mock_parser.config = self._make_mock_config()
        mock_parser.get_constituents.return_value = self._make_mock_constituents()
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)
        updater.update_from_wikipedia('SP500')

        # Second run with identical data
        summary = updater.update_from_wikipedia('SP500')
        assert summary['added_count'] == 0
        assert summary['removed_count'] == 0
        assert summary['unchanged_count'] == 3

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_update_get_constituents_failure_raises(self, mock_parser_cls, index_db):
        from finbase.data.parsers.wikipedia_index_parser import WikipediaIndexParserError
        mock_parser = MagicMock()
        mock_parser.config = self._make_mock_config()
        mock_parser.get_constituents.side_effect = WikipediaIndexParserError("network error")
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)
        with pytest.raises(IndexUpdaterError, match="Failed to fetch constituents"):
            updater.update_from_wikipedia('SP500')


class TestGetUpdateSummary:

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_summary_after_update(self, mock_parser_cls, index_db):
        mock_parser = MagicMock()
        mock_parser.config = {
            'index_code': 'DOW30', 'index_name': 'Dow 30',
            'description': '', 'country': 'US',
            'data_source': 'wikipedia', 'asset_class': 'equity',
            'url': 'https://example.com',
        }
        mock_parser.get_constituents.return_value = pd.DataFrame({
            'symbol': ['AAPL', 'MSFT'],
            'company_name': ['Apple', 'Microsoft'],
            'sector': ['Tech', 'Tech'],
            'source': ['wikipedia'] * 2,
        })
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)
        updater.update_from_wikipedia('DOW30')

        summary = updater.get_update_summary('DOW30')
        assert summary is not None
        assert summary['total_constituents'] == 2
        assert summary['index_code'] == 'DOW30'

    def test_summary_nonexistent_index(self, index_db):
        updater = IndexUpdater(index_db)
        assert updater.get_update_summary('NONEXIST') is None

    @patch('finbase.data.index_updater.WikipediaIndexParser')
    def test_summary_contains_expected_keys(self, mock_parser_cls, index_db):
        mock_parser = MagicMock()
        mock_parser.config = {
            'index_code': 'SP500', 'index_name': 'S&P 500',
            'description': 'Test', 'country': 'US',
            'data_source': 'wikipedia', 'asset_class': 'equity',
            'url': 'https://example.com',
        }
        mock_parser.get_constituents.return_value = pd.DataFrame({
            'symbol': ['AAPL'],
            'company_name': ['Apple'],
            'sector': ['Technology'],
            'source': ['wikipedia'],
        })
        mock_parser_cls.from_index_code.return_value = mock_parser

        updater = IndexUpdater(index_db)
        updater.update_from_wikipedia('SP500')

        summary = updater.get_update_summary('SP500')
        assert summary is not None
        assert 'index_code' in summary
        assert 'index_name' in summary
        assert 'total_constituents' in summary
