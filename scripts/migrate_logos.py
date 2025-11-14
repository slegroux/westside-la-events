"""
Migration script to add source logo URLs to existing events in the database.
"""
import sqlite3
from pathlib import Path
from src.utils.logo_scraper import LogoScraper
import config


def main():
    """Update all events with source logo URLs."""
    print("=" * 60)
    print("Migrating Source Logos to Database")
    print("=" * 60)

    # Initialize logo scraper
    scraper = LogoScraper()

    # Download all logos locally
    print("\nDownloading logos locally...")
    logos = {}
    for source in scraper.SOURCE_URLS.keys():
        local_path = scraper.download_logo(source)
        if local_path:
            logos[source] = local_path
            print(f"  ✓ {source}: {local_path}")
        else:
            print(f"  ✗ {source}: Failed to download")

    print(f"\nSuccessfully downloaded {len(logos)} logos")

    # Connect to database
    db_path = Path(config.DATABASE_PATH)
    if not db_path.exists():
        print(f"\n✗ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get count of events per source
    cursor.execute("SELECT source, COUNT(*) FROM events GROUP BY source")
    source_counts = dict(cursor.fetchall())

    print(f"\nFound events from {len(source_counts)} sources:")
    for source, count in source_counts.items():
        print(f"  - {source}: {count} events")

    # Update each source with its logo URL
    print("\nUpdating events with logo URLs...")
    total_updated = 0

    for source, logo_url in logos.items():
        cursor.execute(
            "UPDATE events SET source_logo_url = ? WHERE source = ?",
            (logo_url, source)
        )
        updated = cursor.rowcount
        total_updated += updated
        if updated > 0:
            print(f"  ✓ Updated {updated} events for {source}")

    conn.commit()
    conn.close()

    print(f"\n✓ Successfully updated {total_updated} events with logo URLs")
    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
