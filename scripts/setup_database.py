"""
Setup script to initialize time series database and load initial data.

The database is stored in user space (~/.finbase/timeseries.db by default)
and configuration is saved to ~/.finbaserc for cross-project access.

Usage:
    python scripts/setup_database.py --init                         # Initialize in default location
    python scripts/setup_database.py --init --db-path /custom/path  # Initialize in custom location
    python scripts/setup_database.py --load-indices                 # Load indices
    python scripts/setup_database.py --load-sp500-top 10            # Load top 10 S&P 500 stocks
    python scripts/setup_database.py --full                         # Full setup
"""

import sys
import os
from pathlib import Path
import argparse
from datetime import datetime
from typing import Optional

from finbase.data.database import TimeSeriesDB
from finbase.data.database.index_db import IndexDB
from finbase.data.loaders import EquityLoader
from finbase.data.risk_factor_groups import (
    RiskFactorGroup,
    EquityRiskFactorGroup,
    MarketCapEnricher,
)
from finbase.data.index_updater import IndexUpdater
from finbase.data.parsers.wikipedia_index_parser import WikipediaIndexParser
from finbase.config.user_config import initialize_user_space
from finbase.config import get_settings
from finbase.utils.logging import configure_application_logging, get_logger

configure_application_logging()
logger = get_logger(__name__)


def initialize_database(db_path: str = None):
    """
    Initialize database schema and user space.

    Args:
        db_path: Optional database path. If None, uses default from Settings.
                 Custom paths are saved to ~/.finbaserc for future use.

    Returns:
        TimeSeriesDB instance
    """
    print("=" * 60)
    print("Initializing Time Series Database")
    print("=" * 60)

    # Determine database path
    if db_path is None:
        # Use default from settings (reads from user config or fallback)
        settings = get_settings()
        db_path = settings.database.path
        print(f"Using default database path from config: {db_path}")
    else:
        # Custom path provided - expand user path
        db_path = str(Path(db_path).expanduser().resolve())
        print(f"Using custom database path: {db_path}")

    # Initialize user space and save config
    actual_db_path = initialize_user_space(Path(db_path))
    print(f"User space initialized: {actual_db_path.parent}")
    print(f"Configuration saved to: ~/.finbaserc")

    # Initialize database schema
    db = TimeSeriesDB(str(actual_db_path))
    db.initialize_schema()

    print(f"\n✓ Database initialized at: {actual_db_path}")
    return db


SP500_GROUP_PATH = "data/risk_factor_groups/equities/sp500.json"


def _build_sp500_config_from_wikipedia() -> dict:
    """Fetch SP500 constituents via the generic parser and shape them
    into a risk-factor-group config dict (the format saved to disk)."""
    parser = WikipediaIndexParser.from_index_code("SP500")
    constituents = parser.get_constituents()
    cfg = parser.config

    # YFinance accepts dot-notation tickers as dashes (BRK.B → BRK-B).
    risk_factors = []
    for _, row in constituents.iterrows():
        risk_factors.append(
            {
                "symbol": str(row["symbol"]).replace(".", "-"),
                "description": row.get("company_name", row["symbol"]),
                "country": cfg.get("country", "US"),
                "currency": cfg.get("currency", "USD"),
                "sector": row.get("sector"),
                "sub_industry": row.get("sub_industry"),
                "headquarters": row.get("headquarters"),
                "date_added": str(row.get("date_added_to_index") or ""),
                "cik": str(row.get("cik") or ""),
                "founded": str(row.get("founded") or ""),
            }
        )

    return {
        "group_name": "sp500",
        "description": "S&P 500 constituents (auto-updated from Wikipedia)",
        "asset_class": "equity",
        "asset_subclass": "stock",
        "data_source": "yfinance",
        "frequency": "daily",
        "update_method": "wikipedia_index_parser",
        "update_url": cfg.get("url"),
        "risk_factors": risk_factors,
    }


def setup_sp500_group():
    """Create and update the S&P 500 group from Wikipedia.

    Always rebuilds the group's risk-factor list from the live Wikipedia
    snapshot. Existing market-cap and category fields would be overwritten
    by this rebuild, so run --update-market-caps afterwards if you want
    them populated.
    """
    print("\n" + "=" * 60)
    print("Setting up S&P 500 Risk Factor Group")
    print("=" * 60)

    print("Fetching SP500 constituents from Wikipedia...")
    config = _build_sp500_config_from_wikipedia()

    # Preserve enriched fields (market_cap, etc.) from the existing file
    # by merging them onto the freshly-fetched factors when possible.
    existing_path = Path(SP500_GROUP_PATH)
    if existing_path.exists():
        existing = RiskFactorGroup(group_path=str(existing_path))
        existing_by_symbol = {
            rf["symbol"]: rf for rf in existing.config.get("risk_factors", [])
        }
        for rf in config["risk_factors"]:
            old = existing_by_symbol.get(rf["symbol"], {})
            if "market_cap" in old:
                rf["market_cap"] = old["market_cap"]
            if "market_cap_category" in old:
                rf["market_cap_category"] = old["market_cap_category"]

    sp500_mgr = EquityRiskFactorGroup(data=config)
    sp500_mgr.save(path=SP500_GROUP_PATH)

    print(f"\n✓ S&P 500 group ready with {sp500_mgr.count()} stocks")
    return sp500_mgr


def update_sp500_market_caps():
    """Enrich the S&P 500 group with market caps via YFinance."""
    print("\n" + "=" * 60)
    print("Updating S&P 500 Market Caps")
    print("=" * 60)
    print("⚠️  This will take 10-15 minutes...")

    sp500 = EquityRiskFactorGroup(group_path=SP500_GROUP_PATH)
    enricher = MarketCapEnricher()
    enricher.enrich(sp500, save_every=50)
    sp500.save()

    print("\n✓ Market caps updated")


def create_sector_subsets():
    """Create sector subset JSON files."""
    print("\n" + "=" * 60)
    print("Creating Sector Subsets")
    print("=" * 60)

    sp500 = EquityRiskFactorGroup("data/risk_factor_groups/equities/sp500.json")

    # Get unique sectors
    sectors = set()
    for rf in sp500.config['risk_factors']:
        if rf.get('sector'):
            sectors.add(rf['sector'])

    print(f"Found {len(sectors)} sectors")

    for sector in sorted(sectors):
        output_path = f"data/risk_factor_groups/equities/sectors/{sector.lower().replace(' ', '_')}.json"
        sp500.create_sector_subset(sector, output_path)

    print(f"\n✓ Created {len(sectors)} sector subset files")


def load_indices(db: TimeSeriesDB, start_date: str = "2005-01-01", max_symbols: int = 10, skip_existing: bool = True):
    """Load index data with rate limiting."""
    print("\n" + "=" * 60)
    print("Loading Index Data")
    print("=" * 60)
    print("⚠️  YFinance rate limiting: 5s/symbol, 30s/10 symbols")
    print(f"⚠️  Recommended: max {max_symbols} symbols per day")
    if skip_existing:
        print("ℹ️  Skipping symbols that already have data")

    end_date = datetime.now().strftime('%Y-%m-%d')

    # Load indices group
    indices = RiskFactorGroup("data/risk_factor_groups/equities/indices.json")

    # Rate limiting comes from Settings.rate_limit (override via FINBASE_YFINANCE_*).
    loader = EquityLoader(db)
    loader.load_from_group(indices, start_date=start_date, end_date=end_date, max_symbols=max_symbols, skip_existing=skip_existing)

    print(f"\n✓ Indices loaded from {start_date} to {end_date}")


def load_sp500_top_n(db: TimeSeriesDB, n: int = 10, start_date: str = "2005-01-01", skip_existing: bool = True):
    """Load top N S&P 500 stocks from the manually curated list (default: 10 to respect rate limits)."""
    print("\n" + "=" * 60)
    print(f"Loading S&P 500 Top {n} Stocks")
    print("=" * 60)
    print("⚠️  YFinance rate limiting: 5s/symbol, 30s/10 symbols")
    print(f"⚠️  Loading {n} symbols will take ~{n * 5 / 60:.1f} minutes")
    if skip_existing:
        print("ℹ️  Skipping symbols that already have data")

    end_date = datetime.now().strftime('%Y-%m-%d')

    sp500 = RiskFactorGroup("data/risk_factor_groups/equities/sp500_top100.json")

    # Get first N symbols from the group
    symbols_to_load = sp500.get_symbols()[:n]

    print(f"Loading {len(symbols_to_load)} stocks...")

    loader = EquityLoader(db)

    for symbol in symbols_to_load:
        rf_data = sp500.get_risk_factor(symbol)
        loader.load_symbol(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            asset_subclass='stock',
            description=rf_data.get('description'),
            country=rf_data.get('country', 'US'),
            currency=rf_data.get('currency', 'USD'),
            sector=rf_data.get('sector'),
            metadata=rf_data,
            skip_existing=skip_existing
        )

    print(f"\n✓ Top {n} stocks loaded from {start_date} to {end_date}")


def load_index_constituents(
    db: TimeSeriesDB,
    index_code: str,
    start_date: str = "2005-01-01",
    max_symbols: Optional[int] = None,
    skip_existing: bool = True
):
    """
    Load historical OHLCV data for all constituents of a specific index.

    Args:
        db: TimeSeriesDB instance
        index_code: Index code (e.g., 'SP500', 'DOW30', 'NDX', 'FTSE100', 'DAX')
        start_date: Start date for historical data (default: 2005-01-01)
        max_symbols: Maximum number of symbols to load (None = all)
        skip_existing: Skip symbols that already have data (default: True)

    Example:
        # Load all DOW30 constituents
        load_index_constituents(db, 'DOW30', start_date='2020-01-01')

        # Load first 10 SP500 constituents
        load_index_constituents(db, 'SP500', max_symbols=10)
    """
    from finbase.data.database.index_db import IndexDB
    from finbase.data.loaders.equity_loader import EquityLoader
    from finbase.data.parsers.wikipedia_index_parser import (
        WikipediaIndexParser,
        WikipediaIndexParserError,
    )

    print("\n" + "=" * 60)
    print(f"Loading {index_code} Constituent Data")
    print("=" * 60)

    # Get index info and constituents
    index_db = IndexDB(db)
    constituents_df = index_db.get_current_constituents(index_code)

    if constituents_df.empty:
        print(f"✗ No constituents found for {index_code}")
        print(f"  Run: python scripts/setup_database.py --update-index {index_code}")
        return

    total_constituents = len(constituents_df)
    symbols_to_load = constituents_df['symbol'].tolist()

    # Apply max_symbols limit if specified
    if max_symbols is not None:
        symbols_to_load = symbols_to_load[:max_symbols]

    print(f"Found {total_constituents} constituents in {index_code}")
    print(f"Loading {len(symbols_to_load)} symbols")
    print(f"Start date: {start_date}")
    print(f"End date: {datetime.now().strftime('%Y-%m-%d')}")
    print()
    print("⚠️  YFinance rate limiting: 5s/symbol, 30s/10 symbols")
    print(f"⚠️  Estimated time: ~{len(symbols_to_load) * 5 / 60:.1f} minutes")
    if skip_existing:
        print("ℹ️  Skipping symbols that already have data")
    print()

    # Resolve country/currency from the index config (single source of truth).
    try:
        index_config = WikipediaIndexParser.from_index_code(index_code).config
    except WikipediaIndexParserError as e:
        print(f"✗ Could not load config for {index_code}: {e}")
        return

    default_country = index_config.get('country', 'US')
    default_currency = index_config.get('currency', 'USD')

    end_date = datetime.now().strftime('%Y-%m-%d')

    loader = EquityLoader(db)

    loaded_count = 0
    skipped_count = 0
    error_count = 0

    for symbol in symbols_to_load:
        # Get constituent metadata
        constituent_row = constituents_df[constituents_df['symbol'] == symbol].iloc[0]

        # Prepare metadata
        description = constituent_row.get('company_name', symbol)
        sector = constituent_row.get('sector')
        country = constituent_row.get('country', default_country)
        currency = default_currency

        try:
            num_records = loader.load_symbol(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                asset_subclass='stock',
                description=description,
                country=country,
                currency=currency,
                sector=sector,
                metadata={'index': index_code},
                skip_existing=skip_existing
            )

            if num_records == 0:
                skipped_count += 1
            else:
                loaded_count += 1

        except Exception as e:
            logger.error(f"Failed to load {symbol}: {e}")
            error_count += 1

    print()
    print(f"✓ {index_code} constituent data loading complete")
    print(f"  Loaded: {loaded_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors: {error_count}")
    print(f"  Total: {loaded_count + skipped_count + error_count}/{len(symbols_to_load)}")


def update_index_constituents(db: TimeSeriesDB, index_code: str):
    """
    Update index constituents from Wikipedia.

    Args:
        db: TimeSeriesDB instance
        index_code: Index code (e.g., 'SP500', 'DOW30')
    """
    print(f"\n{'=' * 60}")
    print(f"Updating {index_code} Constituents")
    print(f"{'=' * 60}")

    try:
        index_db = IndexDB(db)
        updater = IndexUpdater(index_db)

        summary = updater.update_from_wikipedia(index_code)

        print(f"\n✓ {summary['index_name']} updated successfully")
        print(f"  Total constituents: {summary['total_constituents']}")
        print(f"  Added: {summary['added_count']}")
        print(f"  Removed: {summary['removed_count']}")
        print(f"  Unchanged: {summary['unchanged_count']}")

        if summary['added_count'] > 0:
            print(f"\n  New constituents: {', '.join(summary['added_symbols'][:10])}" +
                  (f" and {summary['added_count'] - 10} more" if summary['added_count'] > 10 else ""))
        if summary['removed_count'] > 0:
            print(f"  Removed constituents: {', '.join(summary['removed_symbols'][:10])}" +
                  (f" and {summary['removed_count'] - 10} more" if summary['removed_count'] > 10 else ""))

        print(f"\n  Data source: {summary['data_source']}")
        print(f"  Extracted at: {summary['extraction_time']}")

    except Exception as e:
        print(f"\n✗ Error updating {index_code}: {e}")
        raise


def update_all_indices(db: TimeSeriesDB):
    """Update all configured indices."""
    print(f"\n{'=' * 60}")
    print(f"Updating All Configured Indices")
    print(f"{'=' * 60}")

    try:
        index_db = IndexDB(db)
        updater = IndexUpdater(index_db)

        results = updater.update_all_configured_indices()

        print(f"\n✓ Updated {len(results)} indices:")
        for index_code, summary in results.items():
            if 'error' in summary:
                print(f"  ✗ {index_code}: {summary['error']}")
            else:
                print(f"  ✓ {index_code}: {summary['total_constituents']} constituents " +
                      f"(+{summary['added_count']}, -{summary['removed_count']})")

    except Exception as e:
        print(f"\n✗ Error updating indices: {e}")
        raise


def list_indices(db: TimeSeriesDB):
    """List all registered indices."""
    print(f"\n{'=' * 60}")
    print(f"Registered Indices")
    print(f"{'=' * 60}")

    try:
        index_db = IndexDB(db)
        indices_df = index_db.list_indices()

        if indices_df.empty:
            print("\nNo indices registered yet.")
            print("Run --update-index SP500 to register and load S&P 500.")
            return

        print(f"\nFound {len(indices_df)} registered indices:\n")
        for _, row in indices_df.iterrows():
            print(f"  {row['index_code']}: {row['index_name']}")
            print(f"    Country: {row.get('country', 'N/A')}")
            print(f"    Data source: {row.get('data_source', 'N/A')}")
            print(f"    Last updated: {row.get('last_updated', 'Never')}")

            # Get constituent count
            try:
                constituents_df = index_db.get_current_constituents(row['index_code'])
                print(f"    Current constituents: {len(constituents_df)}")
            except Exception:
                print(f"    Current constituents: 0")
            print()

    except Exception as e:
        print(f"\n✗ Error listing indices: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Setup time series database")
    parser.add_argument("--init", action="store_true", help="Initialize database schema")
    parser.add_argument("--setup-sp500", action="store_true", help="Setup S&P 500 group from Wikipedia")
    parser.add_argument("--update-market-caps", action="store_true", help="Update S&P 500 market caps")
    parser.add_argument("--create-sectors", action="store_true", help="Create sector subset files")
    parser.add_argument("--load-indices", action="store_true", help="Load index data (default: 10 max per day)")
    parser.add_argument("--load-sp500-top", type=int, metavar="N", help="Load top N S&P 500 stocks (default: 10, recommended max/day)")
    parser.add_argument("--max-symbols", type=int, default=10, help="Max symbols to load per run (default: 10)")
    parser.add_argument("--full", action="store_true", help="Full setup (init + sp500 + top 10 + indices)")
    parser.add_argument("--start-date", type=str, default="2005-01-01", help="Start date for data loading (default: 2005-01-01)")
    parser.add_argument("--db-path", type=str, default=None, help="Database path (default: ~/.finbase/timeseries.db or from ~/.finbaserc)")
    parser.add_argument("--force-reload", action="store_true", help="Force reload data even if symbols already exist (default: skip existing)")

    # Index management arguments
    parser.add_argument("--update-index", type=str, action='append', metavar='CODE', help="Update index constituents (e.g., SP500, DOW30)")
    parser.add_argument("--update-all-indices", action="store_true", help="Update all configured indices")
    parser.add_argument("--list-indices", action="store_true", help="List all registered indices")
    parser.add_argument("--load-index-data", type=str, metavar='CODE', help="Load historical OHLCV data for index constituents (e.g., SP500, DOW30, NDX)")
    parser.add_argument("--index-start-date", type=str, default="2005-01-01", help="Start date for index data loading (default: 2005-01-01)")
    parser.add_argument("--index-max-symbols", type=int, help="Max symbols to load from index (default: all)")

    args = parser.parse_args()

    # Convert force_reload to skip_existing (inverse logic)
    skip_existing = not args.force_reload

    # Show help if no arguments
    if len(sys.argv) == 1:
        parser.print_help()
        return

    db = None

    try:
        # Full setup
        if args.full:
            db = initialize_database(args.db_path)
            setup_sp500_group()
            print("\nℹ️  Skipping market cap update (run --update-market-caps separately, takes 10-15 min)")
            create_sector_subsets()
            load_indices(db, args.start_date)
            print("\nℹ️  To load S&P 500 stocks, first run:")
            print("    python scripts/setup_database.py --update-market-caps")
            print("    python scripts/setup_database.py --load-sp500-top 100")
            return

        # Individual steps
        if args.init:
            db = initialize_database(args.db_path)

        if args.setup_sp500:
            setup_sp500_group()

        if args.update_market_caps:
            update_sp500_market_caps()

        if args.create_sectors:
            create_sector_subsets()

        if args.load_indices:
            if db is None:
                db_path = args.db_path or get_settings().database.path
                db = TimeSeriesDB(db_path)
            load_indices(db, args.start_date, max_symbols=args.max_symbols, skip_existing=skip_existing)

        if args.load_sp500_top:
            if db is None:
                db_path = args.db_path or get_settings().database.path
                db = TimeSeriesDB(db_path)
            n = min(args.load_sp500_top, args.max_symbols)  # Respect max_symbols limit
            if args.load_sp500_top > args.max_symbols:
                print(f"⚠️  Requested {args.load_sp500_top} but limiting to {args.max_symbols} (use --max-symbols to override)")
            load_sp500_top_n(db, n, args.start_date, skip_existing=skip_existing)

        # Index management operations
        if args.update_index:
            if db is None:
                db_path = args.db_path or get_settings().database.path
                db = TimeSeriesDB(db_path)
            for index_code in args.update_index:
                update_index_constituents(db, index_code.upper())

        if args.update_all_indices:
            if db is None:
                db_path = args.db_path or get_settings().database.path
                db = TimeSeriesDB(db_path)
            update_all_indices(db)

        if args.list_indices:
            if db is None:
                db_path = args.db_path or get_settings().database.path
                db = TimeSeriesDB(db_path)
            list_indices(db)

        if args.load_index_data:
            if db is None:
                db_path = args.db_path or get_settings().database.path
                db = TimeSeriesDB(db_path)
            load_index_constituents(
                db,
                args.load_index_data.upper(),
                start_date=args.index_start_date,
                max_symbols=args.index_max_symbols,
                skip_existing=skip_existing
            )

        print("\n" + "=" * 60)
        print("✓ Setup Complete!")
        print("=" * 60)

    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    main()
