#!/usr/bin/env python3
"""
Script to geocode remaining events with simpler addresses.
"""
import sqlite3
from src.utils.geocoding import get_geocoding_service
import config

# Simpler address approaches
ADDRESS_OPTIONS = {
    483: [  # Adamson House Garden Tour
        "23200 Pacific Coast Highway, Malibu, CA 90265",
        "Adamson House, Malibu, CA",
        "Malibu Lagoon State Beach, Malibu, CA",
    ],
    65: [  # The Improvised Shakespeare Company
        "366 N La Cienega Blvd, Los Angeles, CA 90048",
        "Largo at the Coronet, Los Angeles, CA",
    ],
    410: [  # Marina del Rey Holiday Boat Parade
        "13650 Mindanao Way, Marina del Rey, CA 90292",
        "Burton Chace Park, Marina del Rey, CA",
    ],
    412: [  # FREE TO SP%@K!
        "3015 Helms Ave, Los Angeles, CA 90034",
        "Village Well, Culver City, CA",
    ],
}

def geocode_remaining_events():
    """Geocode remaining events with multiple address attempts."""
    geocoder = get_geocoding_service()

    # Connect to database
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()

    success_count = 0
    fail_count = 0

    for event_id, address_options in ADDRESS_OPTIONS.items():
        # Get event details
        cursor.execute("""
            SELECT title, venue_name, address, source
            FROM events
            WHERE id = ?
        """, (event_id,))

        row = cursor.fetchone()
        if not row:
            continue

        title, venue_name, original_address, source = row

        print(f"Event {event_id}: {title}")
        print(f"  Source: {source}")
        print(f"  Venue: {venue_name}")
        print(f"  Original Address: {original_address}")

        # Try each address option
        for i, address_attempt in enumerate(address_options, 1):
            print(f"  Attempt {i}: {address_attempt}")

            result = geocoder.geocode(address_attempt)

            if result:
                lat, lng = result
                print(f"  ✓ Geocoded: {lat}, {lng}")

                # Update database
                cursor.execute("""
                    UPDATE events
                    SET latitude = ?, longitude = ?, address = ?, updated_at = datetime('now')
                    WHERE id = ?
                """, (lat, lng, address_attempt, event_id))
                conn.commit()
                success_count += 1
                break
        else:
            print(f"  ✗ All geocoding attempts failed")
            fail_count += 1

        print()

    conn.close()

    print("\n" + "="*60)
    print(f"Geocoding complete!")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")
    print("="*60)

if __name__ == '__main__':
    geocode_remaining_events()
