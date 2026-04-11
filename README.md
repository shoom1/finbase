# FinBase - Historical Financial Data Management

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A simple tool for downloading and storing historical equity data in a local SQLite database. Currently supports equities and major indices via YFinance.

## 🎯 What It Does

- Downloads historical OHLCV data from YFinance
- Stores it in a centralized SQLite database (`~/.finbase/timeseries.db`)
- Tracks index constituents (S&P 500, DOW 30, NASDAQ-100, FTSE 100, DAX)
- Provides a Python API for querying the data

## ✨ Features

- **Index Constituent Tracking**: Historical point-in-time composition for 5 major indices
- **Smart Loading**: Skips existing data, resumable downloads
- **Rate Limiting**: Conservative throttling to avoid hitting YFinance limits
- **DataClient API**: Simple read API for use by other projects

### Index Support

| Index | Constituents | Country | Data Source |
|-------|-------------|---------|-------------|
| S&P 500 | 503 | 🇺🇸 US | Wikipedia |
| DOW 30 | 30 | 🇺🇸 US | Wikipedia |
| NASDAQ-100 | 101 | 🇺🇸 US | Wikipedia |
| FTSE 100 | 100 | 🇬🇧 UK | Wikipedia |
| DAX | 41 | 🇩🇪 Germany | Wikipedia |

### Data Source
- **YFinance**: Equity and index data

## 🚀 Quick Start

### Installation

#### Option 1: Conda (Recommended)
```bash
git clone https://github.com/shoom1/finbase.git
cd finbase
conda env create -f environment.yml
conda activate finbase
```

#### Option 2: Pip
```bash
git clone https://github.com/shoom1/finbase.git
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

- **[QUICK_START_INDEX_DATA.md](docs/QUICK_START_INDEX_DATA.md)** - Loading index data guide
- **[QUICKSTART_INDEX_MANAGEMENT.md](docs/QUICKSTART_INDEX_MANAGEMENT.md)** - Managing indices
- **[DASHBOARD.md](docs/DASHBOARD.md)** - Running the web dashboard
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

### What's Working
- Core database system
- Index management (5 major indices)
- DataClient API
- Smart loading with rate limiting
- Streamlit dashboard

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
