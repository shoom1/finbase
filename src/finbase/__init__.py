"""
FinBase - Financial data management and access package.

Main exports:
- DataClient: High-level API for querying financial data
- TimeSeriesDB: Low-level database access (for internal use)
"""

from importlib.metadata import version, PackageNotFoundError

from .client import DataClient
from .data.database import TimeSeriesDB
from .config import get_settings

try:
    __version__ = version("finbase")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ['DataClient', 'TimeSeriesDB', 'get_settings']
