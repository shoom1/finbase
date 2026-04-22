"""
Example script demonstrating index constituent management.

Shows how to:
1. Update index constituents from Wikipedia
2. Query current and historical constituents
3. Track index changes
4. Check membership
"""

from finbase.data.database import TimeSeriesDB
from finbase.data.database.index_db import IndexDB
from finbase.data.index_updater import IndexUpdater
from finbase.config import get_settings
from finbase.utils.logging import configure_application_logging

def main():
    """Main example function."""
    configure_application_logging()

    print("=" * 80)
    print("Index Constituent Management - Example")
    print("=" * 80)

    # Initialize database
    settings = get_settings()
    db = TimeSeriesDB(settings.database.path)

    # ========================================================================
    # Example 1: Update S&P 500 from Wikipedia
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 1: Update S&P 500 Constituents from Wikipedia")
    print("=" * 80)

    index_db = IndexDB(db)
    updater = IndexUpdater(index_db)

    try:
        summary = updater.update_from_wikipedia('SP500')
        print(f"\n✓ {summary['index_name']} updated successfully")
        print(f"  Total constituents: {summary['total_constituents']}")
        print(f"  Added: {summary['added_count']}")
        print(f"  Removed: {summary['removed_count']}")

        if summary['added_count'] > 0:
            print(f"\n  New constituents: {', '.join(summary['added_symbols'][:5])}" +
                  (f" and {summary['added_count'] - 5} more" if summary['added_count'] > 5 else ""))
    except Exception as e:
        print(f"\n✗ Error: {e}")

    # ========================================================================
    # Example 2: Query Current Constituents
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 2: Query Current S&P 500 Constituents")
    print("=" * 80)

    constituents = index_db.get_current_constituents('SP500')
    print(f"\nCurrent S&P 500: {len(constituents)} companies")

    if not constituents.empty:
        print(f"\nFirst 10 constituents:")
        print(constituents[['symbol', 'company_name', 'sector']].head(10))

        # Sector breakdown
        if 'sector' in constituents.columns:
            print(f"\nTop 5 sectors:")
            sector_counts = constituents['sector'].value_counts().head(5)
            for sector, count in sector_counts.items():
                print(f"  {sector}: {count} companies")

    # ========================================================================
    # Example 3: Check Index Membership
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 3: Check Index Membership")
    print("=" * 80)

    # Check if specific symbols are in S&P 500
    test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'META']
    print(f"\nChecking membership for {', '.join(test_symbols)}:")

    for symbol in test_symbols:
        is_member = index_db.is_index_member(symbol, 'SP500')
        status = "✓ Yes" if is_member else "✗ No"
        print(f"  {symbol}: {status}")

    # ========================================================================
    # Example 4: List All Registered Indices
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 4: List All Registered Indices")
    print("=" * 80)

    indices = index_db.list_indices()
    print(f"\nFound {len(indices)} registered indices:")

    for _, row in indices.iterrows():
        print(f"\n  {row['index_code']}: {row['index_name']}")
        print(f"    Country: {row.get('country', 'N/A')}")
        print(f"    Data source: {row.get('data_source', 'N/A')}")
        print(f"    Last updated: {row.get('last_updated', 'Never')}")

        # Get constituent count
        try:
            constituents = index_db.get_current_constituents(row['index_code'])
            print(f"    Constituents: {len(constituents)}")
        except:
            print(f"    Constituents: 0")

    # ========================================================================
    # Example 5: Using DataClient API
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 5: Using DataClient API")
    print("=" * 80)

    from finbase.client import DataClient

    client = DataClient()

    # Get index constituents
    sp500 = client.get_index_constituents('SP500')
    print(f"\nDataClient.get_index_constituents('SP500'): {len(sp500)} companies")

    # List indices
    indices = client.list_indices()
    print(f"\nDataClient.list_indices(): {len(indices)} indices")

    # Check membership
    is_member = client.is_index_member('AAPL', 'SP500')
    print(f"\nDataClient.is_index_member('AAPL', 'SP500'): {is_member}")

    print("\n" + "=" * 80)
    print("✓ Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
