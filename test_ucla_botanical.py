#!/usr/bin/env python3
"""
Test script for UCLA Botanical Garden scraper.
"""
from src.scrapers.ucla_botanical import UCLABotanicalScraper


def main():
    """Test the UCLA Botanical Garden scraper."""
    print("\n" + "="*60)
    print("Testing UCLA Botanical Garden Scraper")
    print("="*60 + "\n")

    scraper = UCLABotanicalScraper()
    events = scraper.scrape()

    print(f"\n{'='*60}")
    print(f"RESULTS: Found {len(events)} events")
    print("="*60 + "\n")

    if events:
        print("Event Details:\n")
        for i, event in enumerate(events, 1):
            print(f"{i}. {event.title}")
            print(f"   Date: {event.event_date.strftime('%Y-%m-%d %H:%M') if event.event_date else 'N/A'}")
            print(f"   Venue: {event.venue_name}")
            print(f"   Address: {event.address}")
            print(f"   Category: {event.category}")
            print(f"   Price: {'Free' if event.is_free else f'${event.price}' if event.price else 'N/A'}")
            if event.price_note:
                print(f"   Price Note: {event.price_note}")
            print(f"   URL: {event.url}")
            if event.image_url:
                print(f"   Image: {event.image_url}")
            print(f"   Coords: {event.latitude}, {event.longitude}" if event.latitude else "   Coords: Not geocoded")
            print(f"   Description: {event.description[:150]}..." if len(event.description) > 150 else f"   Description: {event.description}")
            print()
    else:
        print("No events found. This could be normal if there are no upcoming events.")


if __name__ == '__main__':
    main()
