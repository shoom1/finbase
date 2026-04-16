"""
Example: extract S&P 500 data with WikipediaIndexParser.

This script shows how to:
1. Extract current S&P 500 constituents
2. Extract historical changes (additions/removals)
3. Export data to CSV/JSON
4. Get summary statistics

The previous version used the now-deprecated SP500WikipediaParser; this
file demonstrates the supported `WikipediaIndexParser.from_index_code`
entry point that works for every shipped index config.
"""

from pathlib import Path

from finbase.data.parsers.wikipedia_index_parser import WikipediaIndexParser


def main():
    """Main example function."""

    print("=" * 80)
    print("S&P 500 Wikipedia Parser - Example")
    print("=" * 80)

    parser = WikipediaIndexParser.from_index_code("SP500")

    # ========================================================================
    # Example 1: Get current constituents
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 1: Extract Current S&P 500 Constituents")
    print("=" * 80)

    constituents = parser.get_constituents()
    print(f"\nTotal constituents: {len(constituents)}")
    print(f"\nColumns: {constituents.columns.tolist()}")
    print("\nFirst 5 constituents:")
    print(constituents.head())

    if "sector" in constituents.columns:
        print("\nSector breakdown:")
        print(constituents["sector"].value_counts())

    # ========================================================================
    # Example 2: Get historical changes
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 2: Extract Historical Changes")
    print("=" * 80)

    changes = parser.get_changes()
    if changes is None or changes.empty:
        print("\nNo historical changes table available for this index.")
    else:
        print(f"\nTotal historical changes: {len(changes)}")
        print(f"\nColumns: {changes.columns.tolist()}")
        print("\nMost recent 10 changes:")
        print(changes.head(10))

        if "added_ticker" in changes.columns:
            recent_additions = changes[changes["added_ticker"].notna()].head(5)
            if not recent_additions.empty:
                print("\nRecent additions:")
                for _, row in recent_additions.iterrows():
                    date = row.get("date", "N/A")
                    ticker = row.get("added_ticker", "N/A")
                    company = row.get("added_company", "N/A")
                    print(f"  {date}: {ticker} - {company}")

        if "removed_ticker" in changes.columns:
            recent_removals = changes[changes["removed_ticker"].notna()].head(5)
            if not recent_removals.empty:
                print("\nRecent removals:")
                for _, row in recent_removals.iterrows():
                    date = row.get("date", "N/A")
                    ticker = row.get("removed_ticker", "N/A")
                    company = row.get("removed_company", "N/A")
                    print(f"  {date}: {ticker} - {company}")

    # ========================================================================
    # Example 3: Get summary statistics
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 3: Summary Statistics")
    print("=" * 80)

    stats = parser.get_summary_stats()
    print(f"\nTotal constituents: {stats['total_constituents']}")
    print(f"Total changes tracked: {stats['total_changes']}")

    if stats.get("sectors"):
        print("\nTop 5 sectors by company count:")
        sorted_sectors = sorted(stats["sectors"].items(), key=lambda x: x[1], reverse=True)
        for sector, count in sorted_sectors[:5]:
            print(f"  {sector}: {count} companies")

    # ========================================================================
    # Example 4: Export to CSV
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 4: Export to CSV")
    print("=" * 80)

    output_dir = Path(__file__).parent.parent / "data" / "sp500"
    csv_files = parser.export_to_csv(output_dir=str(output_dir))
    print("\nExported CSV files:")
    for data_type, filepath in csv_files.items():
        print(f"  {data_type}: {filepath}")

    # ========================================================================
    # Example 5: Export to JSON
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 5: Export to JSON")
    print("=" * 80)

    json_files = parser.export_to_json(output_dir=str(output_dir))
    print("\nExported JSON files:")
    for data_type, filepath in json_files.items():
        print(f"  {data_type}: {filepath}")

    # ========================================================================
    # Example 6: Filter constituents by sector
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 6: Filter by Sector (Information Technology)")
    print("=" * 80)

    if "sector" in constituents.columns:
        tech_companies = constituents[
            constituents["sector"] == "Information Technology"
        ]
        print(f"\nTechnology sector companies: {len(tech_companies)}")
        cols = [
            c
            for c in ("symbol", "company_name", "date_added_to_index")
            if c in tech_companies.columns
        ]
        print("\nTop 10 by ticker:")
        print(tech_companies[cols].head(10))

    # ========================================================================
    # Example 7: Find companies added in a specific year
    # ========================================================================
    print("\n" + "=" * 80)
    print("Example 7: Companies Added in 2024")
    print("=" * 80)

    if "date_added_to_index" in constituents.columns:
        constituents_2024 = constituents[
            constituents["date_added_to_index"].dt.year == 2024
        ]
        print(f"\nCompanies added in 2024: {len(constituents_2024)}")
        if not constituents_2024.empty:
            cols = [
                c
                for c in ("symbol", "company_name", "sector", "date_added_to_index")
                if c in constituents_2024.columns
            ]
            print(constituents_2024[cols])

    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
