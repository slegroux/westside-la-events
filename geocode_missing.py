#!/usr/bin/env python3
"""
Script to geocode events with missing coordinates.
"""
import sqlite3
from src.utils.geocoding import get_geocoding_service
import config

def geocode_missing_events():
    """Geocode all events with NULL latitude or longitude."""
    geocoder = get_geocoding_service()

    # Connect to database
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    # Find events with NULL coordinates
    cursor.execute("""
        SELECT id, title, venue_name, address, source
        FROM events
        WHERE latitude IS NULL OR longitude IS NULL
        ORDER BY source, id
    """)

    events = cursor.fetchall()
    print(f"Found {len(events)} events with missing coordinates\n")

    success_count = 0
    fail_count = 0

    for event_id, title, venue_name, address, source in events:
        print(f"Event {event_id}: {title}")
        print(f"  Source: {source}")
        print(f"  Venue: {venue_name}")
        print(f"  Address: {address}")

        # Try to geocode
        result = geocoder.geocode(address)

        if result:
            lat, lng = result
            print(f"  ✓ Geocoded: {lat}, {lng}")

            # Update database
            cursor.execute("""
                UPDATE events
                SET latitude = ?, longitude = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (lat, lng, event_id))
            conn.commit()
            success_count += 1
        else:
            print(f"  ✗ Geocoding failed")
            fail_count += 1

        print()

    conn.close()

    print("\n" + "="*60)
    print(f"Geocoding complete!")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")
    print("="*60)

if __name__ == '__main__':
    geocode_missing_events()
