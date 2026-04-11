"""
Data parsers for extracting financial information from various sources.

This module contains parsers for extracting data from web sources like Wikipedia,
financial websites, etc.
"""

from .sp500_wikipedia import SP500WikipediaParser
from .wikipedia_index_parser import WikipediaIndexParser

__all__ = ['SP500WikipediaParser', 'WikipediaIndexParser']
