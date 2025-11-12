#!/usr/bin/env python3
"""
Test script to scrape Perry's Beach events from Eventbrite collection page.
"""
import json
import re
from bs4 import BeautifulSoup
import requests

def scrape_perrys_events():
    """Scrape Perry's collection page and extract event URLs."""
    collection_url = 'https://www.eventbrite.com/cc/santa-monica-beach-perrys-beach-events-4542063'

    print("Fetching Perry's collection page...")
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; LAEventsBot/1.0)'}
    response = requests.get(collection_url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"Failed to fetch page: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract event URLs (both relative and absolute)
    event_links = soup.find_all('a', href=re.compile(r'eventbrite\.com/e/[^/]+-tickets-\d+'))
    event_urls = set()

    for link in event_links:
        href = link.get('href', '')
        if '/e/' in href and '-tickets-' in href:
            # Handle both relative and absolute URLs
            if href.startswith('http'):
                clean_url = href.split('?')[0]
            elif href.startswith('/e/'):
                clean_url = f"https://www.eventbrite.com{href.split('?')[0]}"
            else:
                continue
            event_urls.add(clean_url)

    print(f"\nFound {len(event_urls)} unique event URLs:")
    for i, url in enumerate(sorted(event_urls), 1):
        event_title = url.split('/')[-1].replace('-tickets-', ' ').rsplit('-', 1)[0].replace('-', ' ').title()
        print(f"  {i}. {event_title}")
        print(f"     {url}")

    return list(event_urls)

if __name__ == '__main__':
    urls = scrape_perrys_events()
    print(f"\nTotal URLs extracted: {len(urls)}")
