# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-04-22

### Added
- **`symbol_suffix` config field** for `WikipediaIndexParser`. FTSE100
  tickers scraped from Wikipedia are bare (`AAL`, `AZN`) but YFinance
  uses those same symbols for US companies (`AAL` = American Airlines).
  Setting `"symbol_suffix": ".L"` in `ftse100.json` makes the parser
  emit `AAL.L`, `AZN.L`, …, so FinBase stores LSE tickers
  unambiguously. Idempotent — symbols already suffixed are untouched.
- **`match_columns` config field** for `WikipediaIndexParser`. Identifies
  the target table by column headers (structural match) rather than
  positional `table_index`. Protects against Wikipedia fundraising
  banners and other one-off tables that shift subsequent indices.
  Parser logs a warning and uses the first table whose header is a
  superset of `match_columns`; opt-in and backward-compatible.
  Applied to all 5 shipped configs (SP500, DOW30, NDX, FTSE100, DAX).
- **`EquityLoader(ticker_factory=...)`** dependency injection, mirroring
  `MarketCapEnricher`. Alternate data sources and tests no longer need
  to monkeypatch the module-level `yfinance`.
- **`IndexDB`** accepts a `sqlite3.Connection` directly; still accepts
  a `TimeSeriesDB` for backwards compatibility. Stops reaching into
  `TimeSeriesDB`'s private `.conn` attribute from inside IndexDB.
- Test coverage: `TimeSeriesValidator` (previously 206 LOC with zero
  tests), `EquityLoader` DI contract, `IndexDB` connection API,
  `setup_database.py` import safety, parser robustness.

### Changed
- **FTSE100 constituents now stored with `.L` suffix** in
  `index_constituents` and loaded under `.L` in `risk_factors`.
  Back-translation of the existing rows was a one-time SQL update on
  2026-04-20; the parser/config change on this release makes it
  permanent for future `--update-index FTSE100` runs.
- `scripts/setup_database.py`: `configure_application_logging()` moved
  from module scope into `main()`. Importing the script no longer
  reconfigures global logging or creates a `logs/` directory.
- `scripts/setup_database.py`: exits with status 1 when
  `load_index_constituents` reports a non-zero error count, so CI /
  shell automation can detect partial failures.
- Example scripts call `configure_application_logging()` explicitly so
  library output reaches the terminal.
- `TimeSeriesDB.get_risk_factor_info()` now wraps `sqlite3.Error` as
  `DatabaseError`, matching every other read path.

### Fixed
- `TimeSeriesDB.query()` with `start_date=None` or `end_date=None`
  built a `WHERE date >= NULL` clause that silently returned zero
  rows. None bounds now omit their predicate entirely (open range).
- `EquityRiskFactorGroup` god-class split: Wikipedia scraping moved to
  `WikipediaIndexParser`, market-cap enrichment moved to
  `MarketCapEnricher`. `EquityRiskFactorGroup` now holds only the
  subset / top-N operations that depend on an already-loaded group.

---

## [0.1.1] - 2026-04-10

### Changed
- **Project renamed from findata to finbase** for PyPI availability
  - Package: `findata` → `finbase`
  - Config: `~/.findatarc` → `~/.finbaserc`, `~/.findata/` → `~/.finbase/`
  - Env vars: `FINDATA_*` → `FINBASE_*`

### Fixed
- **DataClient.get_data() N+1 query**: queries all symbols at once per column instead of one DB call per symbol×column combination
- **IndexDB connection bypass**: now uses the injected TimeSeriesDB connection instead of opening independent sqlite3 connections per method call
- **Silent data loss in DataClient.get_data()**: unexpected errors now propagate to the caller instead of being silently swallowed; only DatabaseError (no data found) is handled gracefully

---

## [0.1.0] - 2025-12-09

### Added
- **Core Database System**
  - SQLite-based time series database with schema for risk factors and OHLCV data
  - Support for multiple asset classes (equity, fx, rates, commodities)
  - User space configuration (~/.finbase/timeseries.db, ~/.finbaserc)
  - Database audit trail with data_updates table

- **Index Management**
  - Wikipedia-based index constituent extraction
  - Support for 5 major indices: SP500 (503), DOW30 (30), NDX (101), FTSE100 (100), DAX (41)
  - Temporal tracking of index composition (slowly changing dimension pattern)
  - Automatic change detection and logging
  - Config-driven parser for easy addition of new indices

- **Data Loading**
  - YFinance integration with rate limiting (5s/symbol, 30s/batch)
  - Smart loading: automatic skip of existing data
  - Bulk loading by index constituents
  - Incremental and resumable loading
  - Support for US, UK, and German markets

- **DataClient API**
  - Clean API for external projects (e.g., tsgen)
  - Support for long and wide format data
  - Convenience methods: get_closes(), get_latest(), get_all()
  - Discovery methods: list_symbols(), search_symbols(), get_symbol_info()
  - Bulk retrieval by asset class, sector, or index
  - Index constituent queries with historical point-in-time support

- **Risk Factor Groups**
  - JSON-based group definitions
  - Support for equities with sector filtering
  - Market cap sorting and subsetting
  - Built-in groups: major indices, SP500 top companies

- **Dashboard** (Optional)
  - Streamlit-based web dashboard for data exploration
  - Interactive charts with Plotly
  - Database statistics and symbol search
  - Multi-symbol comparison

- **Documentation**
  - Quick start guides for common workflows
  - API examples and usage patterns

### Features
- **Configuration Management**: User-space configuration with ~/.finbaserc
- **Multi-Source Support**: Track data provenance with data_source field
- **Validation**: Input validation and data quality checks
- **Logging**: Comprehensive logging with structured output
- **Testing**: Unit tests for core functionality
- **Error Handling**: Graceful error handling with retries and reporting

### Technical Details
- Python 3.12 required
- SQLite for data storage (<1M records)
- Pandas for data manipulation
- YFinance for market data
- Conda and pip installation support

### Breaking Changes
None (initial release)

### Known Limitations
- YFinance rate limits require conservative loading (10-100 symbols recommended per session)
- SQLite performance degrades >1M records (future: migrate to DuckDB)
- Currently supports daily frequency only
- Index historical changes not fully tracked yet (planned for future release)

### Dependencies
- Core: yfinance, pandas, numpy, lxml, beautifulsoup4, requests, pyyaml
- Development: pytest, pytest-cov
- Dashboard: streamlit, plotly

### Installation
```bash
# From source
git clone https://github.com/yourusername/finbase.git
cd finbase
pip install -e .

# With conda
conda env create -f environment.yml
conda activate finbase
```

---

[0.1.0]: https://github.com/yourusername/finbase/releases/tag/v0.1.0
