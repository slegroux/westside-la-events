#!/usr/bin/env python3
"""
Test script to verify California State Parks scraper geocodes addresses properly.
"""
from src.scrapers.parks_ca import ParksCaliforniaScraper

def test_parks_scraper():
    """Test the California State Parks scraper with geocoding."""
    print("Testing California State Parks Scraper with Geocoding")
    print("=" * 60)

    scraper = ParksCaliforniaScraper()
    events = scraper.scrape()

    print(f"\nScraped {len(events)} events")
    print("\nChecking geocoding results:")
    print("-" * 60)

    for i, event in enumerate(events, 1):
        print(f"\nEvent {i}: {event.title}")
        print(f"  Venue: {event.venue_name}")
        print(f"  Address: {event.address}")
        print(f"  Coordinates: ({event.latitude}, {event.longitude})")

        if event.latitude and event.longitude:
            print(f"  ✓ Successfully geocoded")
        else:
            print(f"  ✗ Missing coordinates")

    # Summary
    geocoded_count = sum(1 for e in events if e.latitude and e.longitude)
    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Total events: {len(events)}")
    print(f"  Geocoded: {geocoded_count}")
    print(f"  Missing coordinates: {len(events) - geocoded_count}")
    print("=" * 60)

if __name__ == '__main__':
    test_parks_scraper()
