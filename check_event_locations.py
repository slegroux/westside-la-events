#!/usr/bin/env python3
"""
Audit script to check which events in the database are actually in the
LA Westside/Malibu coverage area.

Usage:
    micromamba run -n la python check_event_locations.py

Options:
    --show-all: Show all out-of-area events (not just first 20)
    --export: Export results to CSV file
"""

import sqlite3
import sys
import csv
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.geo_filter import (
    is_in_coverage_area,
    is_within_coverage_radius,
    is_westside_address,
    validate_event_location,
    get_location_area,
    haversine_distance,
    SANTA_MONICA_PIER
)


def audit_events(db_path: str = 'data/events.db') -> Dict[str, Any]:
    """
    Audit all events in database to check if they're in coverage area.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dictionary with audit results
    """
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all events
    cursor.execute("""
        SELECT id, title, venue_name, address, latitude, longitude,
               source, event_date, url
        FROM events
        ORDER BY event_date DESC
    """)

    results = {
        'total_events': 0,
        'with_coords': 0,
        'without_coords': 0,
        'in_area': 0,
        'out_of_area': 0,
        'no_location_info': 0,
        'by_source': {},
        'by_area': {'westside': 0, 'malibu': 0, 'outside': 0},
        'outside_events': [],
        'no_location_events': []
    }

    for row in cursor.fetchall():
        results['total_events'] += 1

        # Track by source
        source = row['source'] or 'unknown'
        if source not in results['by_source']:
            results['by_source'][source] = {
                'total': 0, 'in_area': 0, 'out_of_area': 0, 'no_location': 0
            }
        results['by_source'][source]['total'] += 1

        # Validate location
        is_valid, reason = validate_event_location(
            latitude=row['latitude'],
            longitude=row['longitude'],
            address=row['address'],
            venue_name=row['venue_name']
        )

        # Track coordinates availability
        if row['latitude'] and row['longitude']:
            results['with_coords'] += 1
        else:
            results['without_coords'] += 1

        if reason == 'no_location_info':
            results['no_location_info'] += 1
            results['by_source'][source]['no_location'] += 1
            results['no_location_events'].append({
                'id': row['id'],
                'title': row['title'],
                'venue': row['venue_name'],
                'address': row['address'],
                'source': source,
                'url': row['url']
            })
        elif is_valid:
            results['in_area'] += 1
            results['by_source'][source]['in_area'] += 1

            # Determine which area
            if row['latitude'] and row['longitude']:
                area = get_location_area(row['latitude'], row['longitude'])
                results['by_area'][area] += 1
        else:
            results['out_of_area'] += 1
            results['by_source'][source]['out_of_area'] += 1
            results['by_area']['outside'] += 1

            # Calculate distance if coordinates available
            distance = None
            if row['latitude'] and row['longitude']:
                distance = haversine_distance(
                    row['latitude'], row['longitude'],
                    SANTA_MONICA_PIER[0], SANTA_MONICA_PIER[1]
                )

            results['outside_events'].append({
                'id': row['id'],
                'title': row['title'],
                'venue': row['venue_name'],
                'address': row['address'],
                'coords': (row['latitude'], row['longitude']) if row['latitude'] else None,
                'distance_miles': round(distance, 1) if distance else None,
                'source': source,
                'reason': reason,
                'url': row['url'],
                'event_date': row['event_date']
            })

    conn.close()
    return results


def print_report(results: Dict[str, Any], show_all: bool = False):
    """Print formatted audit report."""

    print("\n" + "=" * 80)
    print("EVENT LOCATION AUDIT REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Summary
    print("\n📊 SUMMARY")
    print("-" * 80)
    print(f"Total events:           {results['total_events']:6d}")
    print(f"✓ In coverage area:     {results['in_area']:6d} ({results['in_area']/results['total_events']*100:.1f}%)")
    print(f"✗ Outside area:         {results['out_of_area']:6d} ({results['out_of_area']/results['total_events']*100:.1f}%)")
    print(f"⚠ No location info:     {results['no_location_info']:6d} ({results['no_location_info']/results['total_events']*100:.1f}%)")
    print(f"\nWith coordinates:       {results['with_coords']:6d}")
    print(f"Without coordinates:    {results['without_coords']:6d}")

    # Area breakdown
    print("\n📍 AREA BREAKDOWN (for events in coverage area)")
    print("-" * 80)
    total_in = results['by_area']['westside'] + results['by_area']['malibu']
    if total_in > 0:
        print(f"Westside:               {results['by_area']['westside']:6d} ({results['by_area']['westside']/total_in*100:.1f}%)")
        print(f"Malibu:                 {results['by_area']['malibu']:6d} ({results['by_area']['malibu']/total_in*100:.1f}%)")

    # By source
    print("\n📰 BY SOURCE")
    print("-" * 80)
    print(f"{'Source':<25} {'Total':>8} {'In Area':>10} {'Outside':>10} {'No Loc':>10}")
    print("-" * 80)
    for source, stats in sorted(results['by_source'].items(), key=lambda x: x[1]['total'], reverse=True):
        in_pct = stats['in_area']/stats['total']*100 if stats['total'] > 0 else 0
        print(f"{source:<25} {stats['total']:8d} {stats['in_area']:10d} {stats['out_of_area']:10d} {stats['no_location']:10d}")

    # Outside events
    if results['outside_events']:
        limit = len(results['outside_events']) if show_all else 20
        print(f"\n⚠️  EVENTS OUTSIDE COVERAGE AREA (showing {min(limit, len(results['outside_events']))} of {len(results['outside_events'])})")
        print("-" * 80)

        for i, event in enumerate(results['outside_events'][:limit], 1):
            print(f"\n{i}. {event['title']}")
            print(f"   Source: {event['source']}")
            print(f"   Venue: {event['venue']}")
            print(f"   Address: {event['address']}")
            if event['coords']:
                print(f"   Coordinates: {event['coords']}")
            if event['distance_miles']:
                print(f"   Distance from SM Pier: {event['distance_miles']} miles")
            print(f"   Reason: {event['reason']}")
            if event['url']:
                print(f"   URL: {event['url']}")

        if len(results['outside_events']) > limit:
            print(f"\n   ... and {len(results['outside_events']) - limit} more")
            print(f"   (use --show-all to see all)")

    # No location events
    if results['no_location_events']:
        limit = min(10, len(results['no_location_events']))
        print(f"\n⚠️  EVENTS WITH NO LOCATION INFO (showing {limit} of {len(results['no_location_events'])})")
        print("-" * 80)

        for i, event in enumerate(results['no_location_events'][:limit], 1):
            print(f"\n{i}. {event['title']}")
            print(f"   Source: {event['source']}")
            print(f"   Venue: {event['venue']}")
            print(f"   Address: {event['address']}")

        if len(results['no_location_events']) > limit:
            print(f"\n   ... and {len(results['no_location_events']) - limit} more")

    print("\n" + "=" * 80)


def export_to_csv(results: Dict[str, Any], filename: str = None):
    """Export outside events to CSV file."""
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'outside_events_{timestamp}.csv'

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'id', 'title', 'venue', 'address', 'latitude', 'longitude',
            'distance_miles', 'source', 'reason', 'url', 'event_date'
        ])
        writer.writeheader()

        for event in results['outside_events']:
            row = {
                'id': event['id'],
                'title': event['title'],
                'venue': event['venue'],
                'address': event['address'],
                'latitude': event['coords'][0] if event['coords'] else '',
                'longitude': event['coords'][1] if event['coords'] else '',
                'distance_miles': event['distance_miles'] or '',
                'source': event['source'],
                'reason': event['reason'],
                'url': event['url'],
                'event_date': event['event_date']
            }
            writer.writerow(row)

    print(f"\n✓ Exported {len(results['outside_events'])} outside events to: {filename}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Audit events database for location coverage'
    )
    parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all out-of-area events (not just first 20)'
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export outside events to CSV file'
    )
    parser.add_argument(
        '--db',
        default='data/events.db',
        help='Path to database file (default: data/events.db)'
    )

    args = parser.parse_args()

    print("🔍 Auditing events database...")
    results = audit_events(args.db)

    if results is None:
        sys.exit(1)

    print_report(results, show_all=args.show_all)

    if args.export and results['outside_events']:
        export_to_csv(results)


if __name__ == '__main__':
    main()
