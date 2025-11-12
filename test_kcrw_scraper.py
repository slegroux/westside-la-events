#!/usr/bin/env python3
"""Test KCRW scraper."""

from src.scrapers.kcrw import KCRWScraper

def main():
    scraper = KCRWScraper()
    events = scraper.scrape()

    print(f"\nScraped {len(events)} events\n")

    for i, event in enumerate(events[:5], 1):
        print(f"Event {i}:")
        print(f"  Title: {event.title}")
        print(f"  Date: {event.event_date}")
        print(f"  Venue: {event.venue_name}")
        print(f"  Address: {event.address}")
        print(f"  Category: {event.category}")
        print(f"  URL: {event.url}")
        print(f"  Image: {event.image_url[:60] if event.image_url else 'None'}...")
        print()

if __name__ == '__main__':
    main()
