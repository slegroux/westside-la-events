#!/usr/bin/env python3
"""Test Eventbrite scraper."""

from src.scrapers.eventbrite import EventbriteScraper

def main():
    scraper = EventbriteScraper()
    events = scraper.scrape()

    print(f"\nScraped {len(events)} events\n")
    print("="*80)

    for i, event in enumerate(events[:5], 1):
        print(f"\nEvent {i}:")
        print(f"  Title: {event.title}")
        print(f"  Description: {event.description[:100] if event.description else '(none)'}...")
        print(f"  Venue: {event.venue_name}")
        print(f"  Address: {event.address}")
        print(f"  Coordinates: {event.latitude}, {event.longitude}")
        print(f"  Date: {event.event_date}")
        print(f"  Category: {event.category}")
        print(f"  Price: ${event.price}" if event.price else "  Price: (not specified)")
        print(f"  Free: {event.is_free}")
        print(f"  Image: {event.image_url[:60] if event.image_url else '(none)'}...")
        print(f"  URL: {event.url[:60]}...")

if __name__ == '__main__':
    main()
