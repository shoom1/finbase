"""
FinBase - Financial data management and access package.

Main exports:
- DataClient: High-level API for querying financial data
- TimeSeriesDB: Low-level database access (for internal use)
"""

from .client import DataClient
from .data.database import TimeSeriesDB
from .config import get_settings

__version__ = '0.1.1'

__all__ = ['DataClient', 'TimeSeriesDB', 'get_settings']
