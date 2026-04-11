# FinBase - Historical Financial Data Management

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive system for managing historical financial time series data across multiple asset classes. Built for quantitative researchers, traders, and financial engineers who need reliable, well-organized market data.

## 🎯 Purpose

FinBase is a data management layer designed to:
- Download and store historical OHLCV data from multiple sources
- Maintain a centralized SQLite database of time series
- Track index constituents
- Manage risk factor groups (equities, indices, FX, rates, commodities)
- Provide a clean API for data access by analysis projects

**Philosophy**: Separate data acquisition from data analysis. FinBase handles the messy work of downloading, validating, and organizing financial data so your analysis code stays clean.

## ✨ Features

### Core Capabilities
- **Multi-Asset Support**: Equities, indices, FX (planned), rates (planned), commodities (planned)
- **Index Management**: Track constituents for SP500, DOW30, NASDAQ-100, FTSE 100, DAX
- **Temporal Tracking**: Historical point-in-time index composition queries
- **Smart Loading**: Automatic skip of existing data with resumable downloads
- **Rate Limiting**: Conservative API throttling to respect data provider limits
- **Data Quality**: Metadata tracking, audit trails, validation

### Index Support (v0.1.0)

| Index | Constituents | Country | Data Source |
|-------|-------------|---------|-------------|
| S&P 500 | 503 | 🇺🇸 US | Wikipedia |
| DOW 30 | 30 | 🇺🇸 US | Wikipedia |
| NASDAQ-100 | 101 | 🇺🇸 US | Wikipedia |
| FTSE 100 | 100 | 🇬🇧 UK | Wikipedia |
| DAX | 41 | 🇩🇪 Germany | Wikipedia |

### Data Sources Support
- **YFinance**: Equity and index data (current)
- **FRED API**: US Treasury rates, economic indicators (planned)
- **Alpha Vantage**: FX=, commodity data and alternative equity (planned)
- **Polygon.io**: Alternative equity data (planned)

## 🚀 Quick Start

### Installation

#### Option 1: Conda (Recommended)
```bash
git clone https://github.com/yourusername/finbase.git
cd finbase
conda env create -f environment.yml
conda activate finbase
```

#### Option 2: Pip
```bash
git clone https://github.com/yourusername/finbase.git
cd finbase
pip install -e .

# Or with extras
pip install -e ".[dev,dashboard]"
```

### Basic Usage

#### 1. Initialize Database
```bash
# Creates ~/.finbase/timeseries.db and ~/.finbaserc
python scripts/setup_database.py --init
```

#### 2. Update Index Constituents
```bash
# Get current index memberships from Wikipedia
python scripts/setup_database.py --update-index SP500
python scripts/setup_database.py --update-index DOW30

# Or update all at once
python scripts/setup_database.py --update-all-indices
```

#### 3. Download Historical Data
```bash
# Load price data for all DOW30 constituents
python scripts/setup_database.py --load-index-data DOW30

# Load SP500 from 2020 (faster than full history)
python scripts/setup_database.py --load-index-data SP500 --index-start-date 2020-01-01

# Test with first 10 stocks
python scripts/setup_database.py --load-index-data SP500 --index-max-symbols 10
```

#### 4. Access Data via API
```python
from finbase import DataClient

client = DataClient()

# Get closing prices for portfolio
portfolio = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
prices = client.get_closes(portfolio, start='2020-01-01')

# Get all DOW30 constituents
dow30 = client.get_index_constituents('DOW30')
dow30_prices = client.get_closes(dow30['symbol'].tolist())

# Calculate returns
returns = prices.pct_change()
```

## 📊 Project Structure

```
finbase/
├── src/                          # Source code
│   ├── client/                   # DataClient API for external projects
│   ├── config/                   # Configuration management
│   ├── data/
│   │   ├── database/             # TimeSeriesDB, IndexDB, schema
│   │   ├── loaders/              # EquityLoader (YFinance)
│   │   ├── parsers/              # Wikipedia parsers
│   │   ├── risk_factor_groups/   # Risk factor group management
│   │   └── validators/           # Data validation
│   ├── dashboard/                # Optional Streamlit dashboard
│   └── utils/                    # Logging utilities
│
├── scripts/                      # Command-line scripts
│   └── setup_database.py         # Main data loading script
│
├── data/                         # Data files (created on init)
│   ├── risk_factor_groups/       # JSON group definitions
│   └── index_configs/            # Index configuration files
│
├── examples/                     # Usage examples
│   ├── client_api_examples.py
│   ├── index_management_example.py
│   └── load_index_data_example.py
│
├── tests/                        # Unit tests
└── docs/                         # Quick start guides

User space (created on init):
~/.finbase/
└── timeseries.db                 # SQLite database (shared with other projects)
~/.finbaserc                      # User configuration (YAML)
```

## 📖 Documentation

- **[QUICK_START_INDEX_DATA.md](QUICK_START_INDEX_DATA.md)** - Loading index data guide
- **[QUICKSTART_INDEX_MANAGEMENT.md](QUICKSTART_INDEX_MANAGEMENT.md)** - Managing indices
- **[DASHBOARD.md](DASHBOARD.md)** - Running the web dashboard
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

## 🔑 Key Concepts

### Database Schema

**risk_factors**: Master table with metadata
- symbol, asset_class, asset_subclass
- description, country, currency, sector
- data_source (yfinance, fred, etc.)
- frequency, start_date, end_date

**timeseries_data**: OHLCV price data
- risk_factor_id (FK), date
- open, high, low, close, adj_close, volume
- Optimized indexes for fast queries

**indices**: Index metadata
- index_code, index_name, country
- data_source, last_updated

**index_constituents**: Temporal membership tracking
- index_id, symbol, effective_date, end_date
- Slowly changing dimension pattern for historical queries

### DataClient API

The recommended way to access data from external projects:

```python
from finbase import DataClient

client = DataClient()

# Discovery
stats = client.get_stats()
symbols = client.list_symbols(asset_class='equity', sector='Technology')
info = client.get_symbol_info('AAPL')

# Data Retrieval (long format)
df = client.get_data(['AAPL', 'MSFT'], start='2020-01-01')

# Data Retrieval (wide format for analysis)
prices = client.get_closes(['AAPL', 'MSFT'], start='2020-01-01')

# Index Queries
sp500 = client.get_index_constituents('SP500')
sp500_2020 = client.get_index_constituents('SP500', as_of_date='2020-01-01')

# Bulk Retrieval
tech_stocks = client.get_by_sector('Technology')
```

See `examples/client_api_examples.py` for comprehensive usage.

### Database Performance
- SQLite is optimized for <1M records
- Typical portfolio (100 stocks, 20 years) = ~500K records
- For larger datasets, migration to DuckDB planned for v0.3.0

## 🛠️ Advanced Usage

### Adding New Indices

Create a config file in `data/index_configs/`:

```json
{
  "index_code": "FTSE250",
  "index_name": "FTSE 250",
  "url": "https://en.wikipedia.org/wiki/FTSE_250_Index",
  "country": "GB",
  "asset_class": "equity",
  "data_source": "wikipedia",
  "constituents_table": {
    "table_index": 2,
    "column_mapping": {
      "Company": "company_name",
      "Ticker": "symbol"
    }
  }
}
```

Then run: `python scripts/setup_database.py --update-index FTSE250`

### Custom Risk Factor Groups

Create JSON files in `data/risk_factor_groups/`:

```json
{
  "group_name": "tech_giants",
  "asset_class": "equity",
  "asset_subclass": "stock",
  "data_source": "yfinance",
  "frequency": "daily",
  "risk_factors": [
    {
      "symbol": "AAPL",
      "description": "Apple Inc.",
      "country": "US",
      "currency": "USD",
      "sector": "Technology"
    }
  ]
}
```

### Running the Dashboard

```bash
# Install dashboard dependencies
pip install -e ".[dashboard]"

# Run Streamlit dashboard
streamlit run dashboard_app.py
```

## 🧪 Development

### Running Tests
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=src tests/
```

### Project Status
- ✅ Core database system
- ✅ Index management (5 major indices)
- ✅ DataClient API
- ✅ Smart loading with rate limiting
- ✅ Dashboard
- ⏳ FX data support (planned v0.2.0)
- ⏳ Rates data via FRED (planned v0.2.0)
- ⏳ Alternative data sources (planned v0.3.0)
- ⏳ DuckDB migration (planned v0.3.0)

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
