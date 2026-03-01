"""Test script to verify Venice West scraper with manual pricing overrides."""
import sys
sys.path.insert(0, '/home/sylvain/Projects/LA')

from src.scrapers.venice_west import VeniceWestScraper

def test_venice_west_scraper():
    """Test the Venice West scraper."""
    scraper = VeniceWestScraper()

    print("Testing Venice West scraper...")
    print("=" * 60)

    # Scrape a few events from the calendar
    events = scraper.scrape()

    print(f"\nFound {len(events)} events total")
    print("=" * 60)

    # Look for the Cubensis event
    cubensis_event = None
    for event in events:
        if 'cubensis' in event.title.lower():
            cubensis_event = event
            break

    if cubensis_event:
        print("\nFound Cubensis event:")
        print(f"  Title: {cubensis_event.title}")
        print(f"  Date: {cubensis_event.event_date}")
        print(f"  Venue: {cubensis_event.venue_name}")
        print(f"  URL: {cubensis_event.url}")
        print(f"  Price: ${cubensis_event.price}" if cubensis_event.price else "  Price: Not available")
        print(f"  Free: {cubensis_event.is_free}")
        print(f"  Description: {cubensis_event.description[:200]}...")
    else:
        print("\nCubensis event not found in scraped events")
        print("\nShowing first 3 events:")
        for i, event in enumerate(events[:3], 1):
            print(f"\n{i}. {event.title}")
            print(f"   Date: {event.event_date}")
            print(f"   Price: ${event.price}" if event.price else "   Price: Not available")
            print(f"   URL: {event.url}")

    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == '__main__':
    test_venice_west_scraper()
