# Quick Start: Index Constituent Management

Manage equity index constituents (S&P 500, Dow 30, etc.) with temporal tracking and historical queries.

## CLI Commands

```bash
# Update S&P 500 from Wikipedia
python scripts/setup_database.py --update-index SP500

# Update Dow Jones
python scripts/setup_database.py --update-index DOW30

# Update all configured indices
python scripts/setup_database.py --update-all-indices

# List registered indices
python scripts/setup_database.py --list-indices
```

## DataClient API

### Get Current Constituents

```python
from finbase import DataClient

client = DataClient()

# Get current S&P 500 members
sp500 = client.get_index_constituents('SP500')
print(f"Current S&P 500: {len(sp500)} companies")

# Access data
print(sp500[['symbol', 'company_name', 'sector']].head())
```

### Historical Queries

```python
# Get S&P 500 as of Jan 1, 2020
sp500_2020 = client.get_index_constituents('SP500', as_of_date='2020-01-01')

# Compare current vs historical
current_symbols = set(sp500['symbol'])
historical_symbols = set(sp500_2020['symbol'])

added = current_symbols - historical_symbols
removed = historical_symbols - current_symbols

print(f"Added since 2020: {len(added)}")
print(f"Removed since 2020: {len(removed)}")
```

### Check Membership

```python
# Was Tesla in S&P 500 in December 2020?
client.is_index_member('TSLA', 'SP500', date='2020-12-01')  # False
client.is_index_member('TSLA', 'SP500', date='2021-01-01')  # True

# Is Apple currently in S&P 500?
client.is_index_member('AAPL', 'SP500')  # True
```

### Track Changes

```python
# Get all composition changes in 2024
changes = client.get_index_changes('SP500',
                                   start_date='2024-01-01',
                                   end_date='2024-12-31')

# Filter additions and removals
additions = changes[changes['change_type'] == 'added']
removals = changes[changes['change_type'] == 'removed']

print(f"2024 additions: {len(additions)}")
print(f"2024 removals: {len(removals)}")
```

### List All Indices

```python
indices = client.list_indices()
print(indices[['index_code', 'index_name', 'last_updated']])
```

## Adding New Index

1. Create config file: `data/index_configs/nasdaq100.json`

```json
{
  "index_code": "NDX",
  "index_name": "NASDAQ-100",
  "description": "NASDAQ-100 Index - Top 100 Non-Financial NASDAQ Stocks",
  "country": "US",
  "asset_class": "equity",
  "data_source": "wikipedia",
  "url": "https://en.wikipedia.org/wiki/NASDAQ-100",

  "constituents_table": {
    "table_index": 2,
    "column_mapping": {
      "Ticker": "symbol",
      "Company": "company_name",
      "GICS Sector": "sector"
    }
  }
}
```

2. Update from Wikipedia:

```bash
python scripts/setup_database.py --update-index NDX
```

That's it! No code changes needed.

## Database Schema

### indices table
- index_id, index_code, index_name
- description, country, asset_class
- data_source, created_at, last_updated

### index_constituents table
- constituent_id, index_id, symbol
- effective_date, end_date (NULL = active)
- company_name, sector, sub_industry
- date_added_to_index, extracted_at, data_source

## Run Examples

```bash
# Comprehensive example script
python examples/index_management_example.py
```