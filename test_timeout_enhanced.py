#!/usr/bin/env python3
"""Test enhanced Timeout scraper with detail fetching."""

from src.scrapers.timeout import TimeoutScraper

def main():
    scraper = TimeoutScraper()

    # Modify to test just 1 event
    import requests
    from bs4 import BeautifulSoup

    print("Fetching listing page...")
    html = scraper.fetch_page(scraper.events_url)
    soup = scraper.parse_html(html)

    # Get first event card
    card = soup.find('article', class_='tile')
    if not card:
        print("No event cards found!")
        return

    link_elem = card.find('a', {'data-testid': 'tile-link_testID'})
    if not link_elem:
        print("No link found!")
        return

    url = scraper.normalize_url(link_elem['href'], scraper.base_url)
    print(f"Testing single event: {url}\n")

    # Test detail fetching
    event = scraper._fetch_and_parse_detail(url, card)

    if event:
        print("="*80)
        print("ENHANCED EVENT DATA")
        print("="*80)
        print(f"Title: {event.title}")
        print(f"Description: {event.description[:200] if event.description else '(none)'}...")
        print(f"Venue: {event.venue_name}")
        print(f"Address: {event.address}")
        print(f"Coordinates: {event.latitude}, {event.longitude}")
        print(f"Date: {event.event_date}")
        print(f"End Date: {event.end_date}")
        print(f"Image: {event.image_url[:60] if event.image_url else '(none)'}...")
        print(f"URL: {event.url}")
        print(f"Price: ${event.price}" if event.price else "Price: (not specified)")
        print(f"Free: {event.is_free}")
        print(f"Category: {event.category}")
    else:
        print("Failed to parse event!")

if __name__ == '__main__':
    main()
