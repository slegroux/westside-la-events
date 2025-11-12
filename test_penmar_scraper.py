#!/usr/bin/env python3
"""
Test script for The Penmar scraper.
"""
from src.scrapers.penmar import PenmarScraper


def main():
    """Test The Penmar scraper."""
    print("Testing The Penmar Scraper")
    print("=" * 60)

    scraper = PenmarScraper()
    events = scraper.scrape()

    print(f"\n{'=' * 60}")
    print(f"Total events scraped: {len(events)}")
    print(f"{'=' * 60}\n")

    # Display event details
    for i, event in enumerate(events, 1):
        print(f"\n[Event {i}]")
        print(f"Title: {event.title}")
        print(f"Date: {event.event_date}")
        print(f"Venue: {event.venue_name}")
        print(f"Address: {event.address}")
        print(f"Category: {event.category}")
        print(f"Price: ${event.price}" if event.price else f"Free: {event.is_free}")
        print(f"URL: {event.url}")
        if event.description:
            print(f"Description: {event.description[:150]}...")
        print("-" * 60)


if __name__ == '__main__':
    main()
