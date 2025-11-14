#!/usr/bin/env python3
"""Test script for updated MUD\WTR scraper using Walla API."""

import sys
from src.scrapers.mudwtr import MudWtrScraper


def main():
    """Test the MUD\WTR scraper."""
    print("=" * 60)
    print("Testing MUD\\WTR :gather Scraper (Walla API)")
    print("=" * 60)

    scraper = MudWtrScraper()

    print(f"\nSource: {scraper.source_name}")
    print(f"Website: {scraper.schedule_url}")
    print(f"API: {scraper.api_base_url}")
    print(f"Location ID: {scraper.location_id}")

    print("\n" + "-" * 60)
    print("Fetching classes from Walla API...")
    print("-" * 60 + "\n")

    try:
        events = scraper.scrape()

        print("\n" + "=" * 60)
        print(f"RESULTS: Found {len(events)} events")
        print("=" * 60)

        if events:
            for i, event in enumerate(events[:10], 1):  # Show first 10
                print(f"\n--- Event {i} ---")
                print(f"Title: {event.title}")
                print(f"Date: {event.event_date}")
                print(f"End: {event.end_date}")
                print(f"Price: ${event.price:.2f}" if event.price else "Price: Not specified")
                print(f"Venue: {event.venue_name}")
                print(f"Category: {event.category}")
                print(f"Image: {event.image_url[:60] if event.image_url else 'None'}...")
                if event.description:
                    desc_preview = event.description[:150].replace('\n', ' ')
                    print(f"Description: {desc_preview}...")

            if len(events) > 10:
                print(f"\n... and {len(events) - 10} more events")
        else:
            print("\n⚠ No events found.")
            print("\nThis could mean:")
            print("1. There are no classes scheduled in the next 30 days")
            print("2. The API endpoint or parameters need adjustment")
            print("\nCheck the scraper logs above for more details.")

        return 0

    except Exception as e:
        print(f"\n❌ Error during scrape: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
