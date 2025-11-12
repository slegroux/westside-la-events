#!/usr/bin/env python3
"""Check quality of scraped event data."""

from src.data.database import Database

def main():
    db = Database()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get sample events from each source
        print("="*80)
        print("EVENT DATA QUALITY CHECK")
        print("="*80)

        for source in ['Timeout LA', 'KCRW']:
            print(f"\n{'='*80}")
            print(f"SOURCE: {source}")
            print(f"{'='*80}\n")

            cursor.execute("""
                SELECT title, description, venue_name, address, latitude, longitude, category
                FROM events
                WHERE source = ?
                LIMIT 3
            """, (source,))

            events = cursor.fetchall()

            for i, event in enumerate(events, 1):
                print(f"Event {i}:")
                print(f"  Title: {event[0]}")
                print(f"  Description: {event[1][:100] if event[1] else '(empty)'}...")
                print(f"  Venue: {event[2] or '(empty)'}")
                print(f"  Address: {event[3] or '(empty)'}")
                print(f"  Coords: {event[4], event[5] if event[4] and event[5] else '(empty)'}")
                print(f"  Category: {event[6] or '(empty)'}")
                print()

        # Statistics
        print(f"\n{'='*80}")
        print("STATISTICS")
        print(f"{'='*80}\n")

        cursor.execute("""
            SELECT
                source,
                COUNT(*) as total,
                SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) as has_desc,
                SUM(CASE WHEN venue_name IS NOT NULL AND venue_name != '' THEN 1 ELSE 0 END) as has_venue,
                SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END) as has_coords,
                SUM(CASE WHEN category IS NOT NULL AND category != '' THEN 1 ELSE 0 END) as has_category
            FROM events
            GROUP BY source
        """)

        for row in cursor.fetchall():
            source, total, has_desc, has_venue, has_coords, has_category = row
            print(f"{source}:")
            print(f"  Total events: {total}")
            print(f"  Has description: {has_desc}/{total} ({100*has_desc//total}%)")
            print(f"  Has venue: {has_venue}/{total} ({100*has_venue//total}%)")
            print(f"  Has coordinates: {has_coords}/{total} ({100*has_coords//total}%)")
            print(f"  Has category: {has_category}/{total} ({100*has_category//total}%)")
            print()

if __name__ == '__main__':
    main()
