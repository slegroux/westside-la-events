"""
Script to check for sources in the database that lack logo mappings.
This helps identify when new scrapers are added but their logos aren't configured.
"""
from src.data.database import Database
from src.utils.logo_scraper import LogoScraper
import config


def main():
    """Check for sources missing logo mappings."""
    print("=" * 70)
    print("Checking for Sources Missing Logo Mappings")
    print("=" * 70)

    db = Database(config.DATABASE_PATH)
    scraper = LogoScraper()

    missing_mappings = []

    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT source, COUNT(*) as event_count
            FROM events
            WHERE source IS NOT NULL
            GROUP BY source
            ORDER BY source
        """)

        print("\nSource Status:")
        print("-" * 70)

        for row in cursor.fetchall():
            source, event_count = row
            has_url = source in scraper.SOURCE_URLS
            has_fallback = source in scraper.FALLBACK_LOGOS

            status = "✓" if (has_url and has_fallback) else "⚠️"
            print(f"{status} {source} ({event_count} events)")

            if not has_url:
                print(f"    Missing SOURCE_URLS mapping")
            if not has_fallback:
                print(f"    Missing FALLBACK_LOGOS mapping")

            if not (has_url and has_fallback):
                missing_mappings.append({
                    'source': source,
                    'event_count': event_count,
                    'missing_url': not has_url,
                    'missing_fallback': not has_fallback
                })

    print("\n" + "=" * 70)

    if missing_mappings:
        print(f"⚠️  Found {len(missing_mappings)} sources with missing mappings:")
        print()
        for item in missing_mappings:
            print(f"  {item['source']} ({item['event_count']} events)")
            if item['missing_url']:
                print("    - Add to SOURCE_URLS in src/utils/logo_scraper.py")
            if item['missing_fallback']:
                print("    - Add to FALLBACK_LOGOS in src/utils/logo_scraper.py")
        print("\nAction Required:")
        print("  1. Add missing sources to SOURCE_URLS and FALLBACK_LOGOS")
        print("  2. Run: micromamba run -n la python migrate_logos.py")
    else:
        print("✓ All sources have complete logo mappings!")

    print("=" * 70)


if __name__ == "__main__":
    main()
