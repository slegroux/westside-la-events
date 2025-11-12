"""
Test script for California State Parks scraper.
"""
from src.scrapers.parks_ca import ParksCaliforniaScraper


def main():
    """Test the Parks CA scraper."""
    print("Testing California State Parks scraper...")
    print("-" * 80)

    scraper = ParksCaliforniaScraper()
    events = scraper.scrape()

    print("\n" + "=" * 80)
    print(f"RESULTS: Found {len(events)} events")
    print("=" * 80)

    if events:
        for i, event in enumerate(events, 1):
            print(f"\n{i}. {event.title}")
            print(f"   Venue: {event.venue_name}")
            print(f"   Address: {event.address}")
            print(f"   Date: {event.event_date}")
            print(f"   Category: {event.category}")
            if event.price:
                print(f"   Price: ${event.price}")
            elif event.is_free:
                print(f"   Price: Free")
            if event.price_note:
                print(f"   Note: {event.price_note}")
            print(f"   URL: {event.url}")
            if event.description:
                desc_preview = event.description[:200] + "..." if len(event.description) > 200 else event.description
                print(f"   Description: {desc_preview}")
    else:
        print("\nNo events found. This could mean:")
        print("1. There are no events in the Angeles District currently")
        print("2. The website structure has changed")
        print("3. There was an error during scraping (check logs above)")


if __name__ == "__main__":
    main()
