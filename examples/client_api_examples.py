"""
Examples of using the FinBase DataClient API.

This demonstrates how external projects can access FinBase without direct database access.
"""

from finbase.client import DataClient

# Initialize client (auto-finds database via ~/.finbaserc)
client = DataClient()

# ============================================================================
# EXAMPLE 1: Discovery - What data is available?
# ============================================================================

print("=" * 70)
print("EXAMPLE 1: Discovering Available Data")
print("=" * 70)

# Get database statistics
stats = client.get_stats()
print(f"\nDatabase Statistics:")
print(f"  Total symbols: {stats['total_symbols']}")
print(f"  Asset classes: {stats['asset_classes']}")
print(f"  Data sources: {stats['data_sources']}")
print(f"  Date range: {stats['date_range']}")

# List all symbols
all_symbols = client.list_symbols()
print(f"\nAll symbols ({len(all_symbols)}): {all_symbols[:10]}...")

# List filtered symbols
tech_symbols = client.list_symbols(asset_class='equity', sector='Technology')
print(f"\nTechnology stocks: {tech_symbols}")

# Search for symbols
aa_symbols = client.search_symbols(pattern='A*')
print(f"\nSymbols starting with 'A': {aa_symbols['symbol'].tolist()}")

# ============================================================================
# EXAMPLE 2: Metadata - Get information about a symbol
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 2: Getting Symbol Metadata")
print("=" * 70)

# Get detailed info
info = client.get_symbol_info('AAPL')
print(f"\nAAPL Information:")
print(f"  Description: {info['description']}")
print(f"  Asset class: {info['asset_class']}")
print(f"  Sector: {info['sector']}")
print(f"  Country: {info['country']}")
print(f"  Currency: {info['currency']}")
print(f"  Data source: {info['data_source']}")
print(f"  Date range: {info['start_date']} to {info['end_date']}")

# Check if symbol exists
if client.has_symbol('AAPL'):
    print("\n✅ AAPL exists in database")

# Get date range
start, end = client.get_date_range('AAPL')
print(f"AAPL data available from {start} to {end}")

# ============================================================================
# EXAMPLE 3: Simple Data Retrieval - Single symbol
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 3: Retrieving Data for Single Symbol")
print("=" * 70)

# Get closing prices (long format)
df = client.get_data('AAPL', columns=['close'], start='2024-01-01', end='2024-01-10')
print(f"\nAAPL closing prices (long format):")
print(df.head())

# Get multiple columns (long format)
df_multi = client.get_data(
    'AAPL',
    columns=['close', 'volume'],
    start='2024-01-01',
    end='2024-01-05'
)
print(f"\nAAPL with multiple columns:")
print(df_multi)

# Get all OHLCV data
df_all = client.get_data('AAPL', start='2024-01-02', end='2024-01-03')
print(f"\nAAPL all columns (first few rows):")
print(df_all.head(10))

# ============================================================================
# EXAMPLE 4: Multiple Symbols
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 4: Retrieving Data for Multiple Symbols")
print("=" * 70)

# Get data for portfolio (long format)
portfolio = ['AAPL', 'MSFT', 'GOOGL']
df_portfolio = client.get_data(
    portfolio,
    columns=['close'],
    start='2024-01-02',
    end='2024-01-05'
)
print(f"\nPortfolio data (long format):")
print(df_portfolio)

# Get data in wide format for analysis
df_wide = client.get_data(
    portfolio,
    columns=['close', 'volume'],
    start='2024-01-02',
    end='2024-01-04',
    format='wide'
)
print(f"\nPortfolio data (wide format):")
print(df_wide)

# ============================================================================
# EXAMPLE 5: Convenience Methods
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 5: Using Convenience Methods")
print("=" * 70)

# Get closing prices in wide format (ready for analysis)
closes = client.get_closes(['AAPL', 'MSFT', 'GOOGL'], start='2024-01-02', end='2024-01-05')
print(f"\nClosing prices (wide format):")
print(closes)

# Get latest 5 days of data
latest = client.get_latest('AAPL', days=5, columns=['close'])
print(f"\nLatest 5 days for AAPL:")
print(latest)

# Get all available data
all_data = client.get_all('AAPL', columns=['close'])
print(f"\nAll AAPL data: {len(all_data)} rows")
print(f"Date range: {all_data['date'].min()} to {all_data['date'].max()}")

# ============================================================================
# EXAMPLE 6: Bulk Retrieval by Category
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 6: Bulk Retrieval by Category")
print("=" * 70)

# Get all equity data
equity_data = client.get_by_asset_class(
    'equity',
    columns=['close'],
    start='2024-01-02',
    end='2024-01-03'
)
print(f"\nAll equity data: {len(equity_data)} rows")
print(equity_data.head(10))

# Get all technology stocks
tech_data = client.get_by_sector(
    'Technology',
    columns=['close'],
    start='2024-01-02',
    end='2024-01-03'
)
print(f"\nTechnology sector data: {len(tech_data)} rows")
print(f"Symbols: {tech_data['symbol'].unique()}")

# ============================================================================
# EXAMPLE 7: Working with the Long Format
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 7: Analyzing Long Format Data")
print("=" * 70)

# Get data in long format
df_long = client.get_data(
    ['AAPL', 'MSFT'],
    columns=['close', 'volume'],
    start='2024-01-02',
    end='2024-01-05'
)

# Easy filtering
aapl_only = df_long[df_long['symbol'] == 'AAPL']
print(f"\nFiltered to AAPL only:")
print(aapl_only.head())

# Easy grouping
by_symbol = df_long[df_long['metric'] == 'close'].groupby('symbol')['value'].mean()
print(f"\nAverage closing prices:")
print(by_symbol)

# Pivot to wide format when needed
df_pivot = df_long.pivot_table(
    index='date',
    columns=['symbol', 'metric'],
    values='value'
)
print(f"\nCustom pivot:")
print(df_pivot)

# ============================================================================
# EXAMPLE 8: Use in External Project (tsgen simulation)
# ============================================================================

print("\n" + "=" * 70)
print("EXAMPLE 8: Simulated tsgen Project Usage")
print("=" * 70)

# Simulate how tsgen would use this API
print("\n# In tsgen project:")
print("from finbase import DataClient")
print()
print("client = DataClient()")
print()

# Get universe of stocks
universe = client.list_symbols(asset_class='equity')
print(f"universe = client.list_symbols(asset_class='equity')")
print(f"# Returns: {universe[:5]}... ({len(universe)} total)")
print()

# Get historical data for backtest
backtest_data = client.get_closes(
    universe[:5],  # First 5 for example
    start='2023-01-01',
    end='2023-12-31'
)
print(f"data = client.get_closes(universe, start='2023-01-01', end='2023-12-31')")
print(f"# Returns DataFrame: {backtest_data.shape}")
print()

# Calculate returns
print("returns = data.pct_change()")
print("# Ready for strategy backtesting!")

print("\n" + "=" * 70)
print("✅ All examples completed successfully!")
print("=" * 70)
