#!/usr/bin/env python3
"""
Test script for Venice West scraper.
"""
from src.scrapers.venice_west import VeniceWestScraper


def test_scraper():
    """Test the Venice West scraper."""
    print("="*80)
    print("Testing Venice West Scraper")
    print("="*80)

    scraper = VeniceWestScraper()

    print(f"\nSource: {scraper.source_name}")
    print(f"URL: {scraper.calendar_url}")
    print(f"Venue: {scraper.venue_name}")
    print(f"Address: {scraper.venue_address}")

    print("\n" + "-"*80)
    print("Starting scrape...")
    print("-"*80)

    events = scraper.scrape()

    print("\n" + "="*80)
    print(f"SCRAPE COMPLETE: Found {len(events)} events")
    print("="*80)

    if events:
        print("\nFirst 5 events:")
        for i, event in enumerate(events[:5], 1):
            print(f"\n{i}. {event.title}")
            print(f"   Date: {event.event_date}")
            print(f"   Venue: {event.venue_name}")
            print(f"   Address: {event.address}")
            print(f"   Category: {event.category}")
            print(f"   Free: {event.is_free}")
            print(f"   URL: {event.url}")
            if event.image_url:
                print(f"   Image: {event.image_url[:80]}...")
            if event.latitude and event.longitude:
                print(f"   Coordinates: ({event.latitude}, {event.longitude})")

        print(f"\n... and {len(events) - 5} more events" if len(events) > 5 else "")

        # Category breakdown
        categories = {}
        for event in events:
            categories[event.category] = categories.get(event.category, 0) + 1

        print("\nCategory breakdown:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            print(f"   {cat}: {count}")

        # Free vs paid
        free_count = sum(1 for e in events if e.is_free)
        print(f"\nFree events: {free_count}")
        print(f"Paid events: {len(events) - free_count}")

    else:
        print("\n⚠ No events found!")


if __name__ == '__main__':
    test_scraper()
