#!/usr/bin/env python3
"""
Script to geocode events with missing coordinates using improved addresses.
"""
import sqlite3
from src.utils.geocoding import get_geocoding_service
import config

# Manual address improvements for known locations
ADDRESS_IMPROVEMENTS = {
    "Malibu Creek SP, Los Angeles, CA": "Malibu Creek State Park, 1925 Las Virgenes Rd, Calabasas, CA 91302",
    "Malibu Lagoon SB, Los Angeles, CA": "Malibu Lagoon State Beach, 23200 Pacific Coast Highway, Malibu, CA 90265",
    "Main Trailhead Parking Lot": "Malibu Creek State Park, 1925 Las Virgenes Rd, Calabasas, CA 91302",
    "Largo at the Coronet, West Hollywood, Los Angeles, CA": "Largo at the Coronet, 366 N La Cienega Blvd, Los Angeles, CA 90048",
    "Burton Chace Park, Venice, Los Angeles, CA": "Burton Chace Park, 13650 Mindanao Way, Marina del Rey, CA 90292",
    "Village Well Books & Coffee, Palms, Los Angeles, CA": "Village Well Books & Coffee, 3015 Helms Ave, Los Angeles, CA 90034",
    "707 Tiverton Drive, Los Angeles, CA 90095, Los Angeles CA 90095": "707 Tiverton Drive, Los Angeles, CA 90095",
}

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
        print(f"  Original Address: {address}")

        # Check if we have an improved address
        improved_address = ADDRESS_IMPROVEMENTS.get(address, address)
        if improved_address != address:
            print(f"  Improved Address: {improved_address}")

        # Try to geocode
        result = geocoder.geocode(improved_address)

        if result:
            lat, lng = result
            print(f"  ✓ Geocoded: {lat}, {lng}")

            # Update database with both new coordinates and improved address
            cursor.execute("""
                UPDATE events
                SET latitude = ?, longitude = ?, address = ?, updated_at = datetime('now')
                WHERE id = ?
            """, (lat, lng, improved_address, event_id))
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
