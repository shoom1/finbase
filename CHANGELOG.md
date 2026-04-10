# Changelog

All notable changes to this project will be documented in this file.

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
