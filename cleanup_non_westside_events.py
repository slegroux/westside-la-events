#!/usr/bin/env python3
"""
Cleanup script to remove events outside Westside/Malibu coverage area from database.

This script removes events that were scraped before the geographic filtering was added
to the scrapers. It validates each event's location and removes those that fall outside
the coverage area.

Usage:
    micromamba run -n la python cleanup_non_westside_events.py [--dry-run]

Options:
    --dry-run: Show what would be deleted without actually deleting
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.geo_filter import (
    validate_event_location,
    get_location_area,
    haversine_distance,
    SANTA_MONICA_PIER
)


def cleanup_database(db_path: str = 'data/events.db', dry_run: bool = False):
    """
    Remove events outside coverage area from database.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, show what would be deleted without deleting
    """
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all events
    cursor.execute("""
        SELECT id, title, venue_name, address, latitude, longitude, source, event_date
        FROM events
    """)

    events = cursor.fetchall()
    total_events = len(events)

    to_delete = []
    to_keep = []

    print(f"🔍 Analyzing {total_events} events...")
    print("=" * 80)

    for row in events:
        is_valid, reason = validate_event_location(
            latitude=row['latitude'],
            longitude=row['longitude'],
            address=row['address'],
            venue_name=row['venue_name']
        )

        if is_valid:
            to_keep.append(row['id'])
        else:
            distance = None
            if row['latitude'] and row['longitude']:
                distance = haversine_distance(
                    row['latitude'], row['longitude'],
                    SANTA_MONICA_PIER[0], SANTA_MONICA_PIER[1]
                )

            to_delete.append({
                'id': row['id'],
                'title': row['title'],
                'venue': row['venue_name'],
                'address': row['address'],
                'source': row['source'],
                'distance': distance,
                'reason': reason
            })

    # Print summary
    print(f"\n📊 SUMMARY")
    print("-" * 80)
    print(f"Total events:           {total_events}")
    print(f"✓ Keep (in area):       {len(to_keep)} ({len(to_keep)/total_events*100:.1f}%)")
    print(f"✗ Delete (outside):     {len(to_delete)} ({len(to_delete)/total_events*100:.1f}%)")

    if to_delete:
        # Group by source
        by_source = {}
        for event in to_delete:
            source = event['source'] or 'unknown'
            if source not in by_source:
                by_source[source] = 0
            by_source[source] += 1

        print(f"\n📰 EVENTS TO DELETE BY SOURCE")
        print("-" * 80)
        for source, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True):
            print(f"  {source:30s} {count:4d}")

        print(f"\n⚠️  SAMPLE OF EVENTS TO DELETE (first 10)")
        print("-" * 80)
        for i, event in enumerate(to_delete[:10], 1):
            print(f"\n{i}. {event['title']}")
            print(f"   Source: {event['source']}")
            print(f"   Venue: {event['venue']}")
            if event['distance']:
                print(f"   Distance: {event['distance']:.1f} miles from SM Pier")
            print(f"   Reason: {event['reason']}")

        if len(to_delete) > 10:
            print(f"\n   ... and {len(to_delete) - 10} more")

    # Perform deletion if not dry run
    if not dry_run and to_delete:
        print("\n" + "=" * 80)
        response = input(f"⚠️  Delete {len(to_delete)} events? [y/N]: ")

        if response.lower() == 'y':
            delete_ids = [event['id'] for event in to_delete]

            # Delete in batches
            batch_size = 100
            deleted_count = 0

            for i in range(0, len(delete_ids), batch_size):
                batch = delete_ids[i:i+batch_size]
                placeholders = ','.join('?' * len(batch))
                cursor.execute(f"DELETE FROM events WHERE id IN ({placeholders})", batch)
                deleted_count += len(batch)

            conn.commit()
            print(f"\n✅ Deleted {deleted_count} events outside coverage area")
            print(f"✅ Kept {len(to_keep)} events in Westside/Malibu")
        else:
            print("\n❌ Deletion cancelled")
    elif dry_run:
        print("\n" + "=" * 80)
        print("🔍 DRY RUN - No changes made to database")
        print(f"   Run without --dry-run to delete {len(to_delete)} events")

    conn.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Clean up non-Westside events from database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--db',
        default='data/events.db',
        help='Path to database file (default: data/events.db)'
    )

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 Running in DRY RUN mode - no changes will be made\n")

    cleanup_database(args.db, args.dry_run)


if __name__ == '__main__':
    main()
