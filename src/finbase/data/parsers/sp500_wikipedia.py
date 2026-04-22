"""
Deprecated S&P 500 Wikipedia parser.

This module exists only as a back-compat shim. The class is a thin
subclass of :class:`WikipediaIndexParser` configured against the SP500
config that ships with the package (``finbase/index_configs/sp500.json``).

New code should use ``WikipediaIndexParser.from_index_code('SP500')``
directly. Instantiating ``SP500WikipediaParser`` raises a
``DeprecationWarning`` to nudge consumers in that direction.
"""

import warnings
from typing import Optional

from .wikipedia_index_parser import WikipediaIndexParser, WikipediaIndexParserError


class SP500ParserError(Exception):
    """Back-compat alias for parsing errors raised by the SP500 wrapper."""

    pass


class SP500WikipediaParser(WikipediaIndexParser):
    """
    Deprecated. Use ``WikipediaIndexParser.from_index_code('SP500')``.

    Behaves identically to the generic parser loaded with the SP500 config
    and additionally exposes legacy method aliases (``get_current_constituents``
    and ``get_historical_changes``) so older callers still work while they
    migrate.
    """

    WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    def __init__(self, url: Optional[str] = None):
        warnings.warn(
            "SP500WikipediaParser is deprecated; use "
            "WikipediaIndexParser.from_index_code('SP500') instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        try:
            base = WikipediaIndexParser.from_index_code("SP500")
        except WikipediaIndexParserError as e:
            raise SP500ParserError(f"Failed to load SP500 config: {e}") from e

        config = dict(base.config)
        if url is not None:
            config["url"] = url

        super().__init__(config)

    # ------------------------------------------------------------------
    # Legacy method aliases — names the original specialized parser used.
    # ------------------------------------------------------------------

    def get_current_constituents(self):
        """Alias for :meth:`WikipediaIndexParser.get_constituents`."""
        try:
            return self.get_constituents()
        except WikipediaIndexParserError as e:
            raise SP500ParserError(str(e)) from e

    def get_historical_changes(self):
        """Alias for :meth:`WikipediaIndexParser.get_changes`. Returns
        an empty DataFrame instead of None when no changes exist, matching
        the legacy contract."""
        import pandas as pd

        try:
            changes = self.get_changes()
        except WikipediaIndexParserError as e:
            raise SP500ParserError(str(e)) from e
        if changes is None:
            return pd.DataFrame()
        return changes

    def fetch_page(self):
        """Wraps the parent fetch with the legacy error type."""
        try:
            return super().fetch_page()
        except WikipediaIndexParserError as e:
            raise SP500ParserError(str(e)) from e

    def _parse_tables(self):
        """Wraps the parent table parser with the legacy error type."""
        try:
            return super()._parse_tables()
        except WikipediaIndexParserError as e:
            raise SP500ParserError(str(e)) from e
