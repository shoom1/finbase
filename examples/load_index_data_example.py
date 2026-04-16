"""
Example: Loading historical OHLCV data for index constituents.

This example shows how to download historical price data for all stocks
in a specific index (SP500, DOW30, NDX, FTSE100, DAX).
"""

from finbase.data.database import TimeSeriesDB
from finbase.data.database.index_db import IndexDB
from finbase.data.loaders import EquityLoader

def load_dow30_example():
    """Load historical data for all DOW30 constituents."""

    # Connect to database
    with TimeSeriesDB() as db:
        # Get DOW30 constituents
        index_db = IndexDB(db)
        constituents_df = index_db.get_current_constituents('DOW30')

        print(f"DOW30 has {len(constituents_df)} constituents")
        print(f"Symbols: {constituents_df['symbol'].tolist()}")

        # Load first 5 for demonstration
        symbols_to_load = constituents_df['symbol'].tolist()[:5]

        # Create loader (rate limits come from Settings.rate_limit)
        loader = EquityLoader(db)

        # Load each symbol
        for symbol in symbols_to_load:
            print(f"\nLoading {symbol}...")
            constituent_row = constituents_df[constituents_df['symbol'] == symbol].iloc[0]

            loader.load_symbol(
                symbol=symbol,
                start_date='2020-01-01',
                end_date='2023-12-31',
                asset_subclass='stock',
                description=constituent_row.get('company_name', symbol),
                country='US',
                currency='USD',
                sector=constituent_row.get('sector'),
                metadata={'index': 'DOW30'},
                skip_existing=True
            )

        print("\n✓ Data loading complete!")

if __name__ == "__main__":
    load_dow30_example()
