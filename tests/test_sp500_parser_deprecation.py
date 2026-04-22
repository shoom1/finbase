"""
Pin SP500WikipediaParser to its deprecated-wrapper status.

After H3, SP500WikipediaParser exists only as a back-compat shim around
WikipediaIndexParser. Instantiation must raise DeprecationWarning, and the
class must subclass WikipediaIndexParser so all the generic features work
without re-implementation.
"""

import warnings

import pytest

from finbase.data.parsers.sp500_wikipedia import SP500WikipediaParser
from finbase.data.parsers.wikipedia_index_parser import WikipediaIndexParser


class TestSP500WikipediaParserIsDeprecatedWrapper:
    def test_subclass_of_wikipedia_index_parser(self):
        assert issubclass(SP500WikipediaParser, WikipediaIndexParser)

    def test_instantiation_emits_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="WikipediaIndexParser"):
            SP500WikipediaParser()

    def test_inherits_export_methods(self):
        # `hasattr` is enough — these come from the generic parser.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            parser = SP500WikipediaParser()
        assert callable(getattr(parser, "export_to_csv", None))
        assert callable(getattr(parser, "export_to_json", None))
        assert callable(getattr(parser, "get_summary_stats", None))

    def test_loads_sp500_config(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            parser = SP500WikipediaParser()
        assert parser.index_code == "SP500"
        assert parser.config.get("country") == "US"
        assert parser.config.get("currency") == "USD"
