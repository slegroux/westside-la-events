#!/usr/bin/env python3
"""Analyze Eventbrite structure for scraping."""

import requests
from bs4 import BeautifulSoup
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Eventbrite search for Los Angeles events
url = "https://www.eventbrite.com/d/ca--los-angeles/events/"
print(f"Fetching: {url}\n")

r = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

# Save HTML for analysis
with open('eventbrite_listing.html', 'w') as f:
    f.write(soup.prettify())
print("Saved HTML to: eventbrite_listing.html\n")

print("="*80)
print("EVENTBRITE LISTING PAGE STRUCTURE")
print("="*80)

# Look for event cards
print("\nSearching for event containers...")

# Common patterns
patterns = ['event', 'card', 'search-event', 'discover']

for pattern in patterns:
    elements = soup.find_all(class_=lambda x: x and pattern in str(x).lower())
    if elements:
        unique_classes = set()
        for elem in elements[:10]:
            if elem.get('class'):
                unique_classes.update(elem['class'])
        if unique_classes:
            print(f"\n  Classes containing '{pattern}': {len(elements)} elements")
            for cls in sorted(unique_classes)[:10]:
                print(f"    - {cls}")

# Look for structured data
json_lds = soup.find_all('script', type='application/ld+json')
print(f"\n\nFound {len(json_lds)} JSON-LD scripts")
for i, json_ld in enumerate(json_lds[:2], 1):
    print(f"\n--- JSON-LD {i} ---")
    try:
        data = json.loads(json_ld.string)
        print(json.dumps(data, indent=2)[:500])
    except:
        print("Failed to parse")

# Look for Next.js data (Eventbrite might use Next.js)
next_data = soup.find('script', id='__NEXT_DATA__')
if next_data:
    print("\n\n=== NEXT.JS DATA FOUND ===")
    try:
        data = json.loads(next_data.string)
        # Eventbrite often stores event data here
        print("Keys:", list(data.keys())[:10])
        if 'props' in data:
            print("Props keys:", list(data['props'].keys())[:10])
    except:
        print("Failed to parse Next.js data")

# Look for data attributes
data_attrs = soup.find_all(attrs={'data-event-id': True})
print(f"\n\nFound {len(data_attrs)} elements with data-event-id")

# Look for links to events
event_links = soup.find_all('a', href=lambda x: x and '/e/' in str(x))
print(f"\nFound {len(event_links)} event links")
if event_links:
    print("\nSample event URLs:")
    for link in event_links[:5]:
        href = link.get('href')
        if href and '/e/' in href:
            print(f"  {href}")

# If we found an event link, fetch detail page
if event_links:
    sample_url = event_links[0].get('href')
    if sample_url and sample_url.startswith('http'):
        print(f"\n\n{'='*80}")
        print("EVENTBRITE DETAIL PAGE STRUCTURE")
        print(f"{'='*80}")
        print(f"\nFetching: {sample_url}\n")

        r_detail = requests.get(sample_url, headers=headers, timeout=10)
        soup_detail = BeautifulSoup(r_detail.text, 'html.parser')

        # Look for structured data
        json_lds_detail = soup_detail.find_all('script', type='application/ld+json')
        print(f"Found {len(json_lds_detail)} JSON-LD scripts on detail page")
        for i, json_ld in enumerate(json_lds_detail[:1], 1):
            print(f"\n--- JSON-LD {i} ---")
            try:
                data = json.loads(json_ld.string)
                print(json.dumps(data, indent=2)[:800])
            except:
                print("Failed to parse")

        # Look for Next.js data
        next_data_detail = soup_detail.find('script', id='__NEXT_DATA__')
        if next_data_detail:
            print("\n\n=== DETAIL PAGE NEXT.JS DATA FOUND ===")
            try:
                data = json.loads(next_data_detail.string)
                # Try to find event data
                if 'props' in data and 'pageProps' in data['props']:
                    props = data['props']['pageProps']
                    if 'event' in props:
                        print("\nEvent data found in Next.js!")
                        event = props['event']
                        print(f"Title: {event.get('name', 'N/A')}")
                        print(f"Description: {event.get('summary', 'N/A')[:100]}...")
                        print(f"Start: {event.get('start', {}).get('local', 'N/A')}")
                        if 'venue' in event:
                            venue = event['venue']
                            print(f"Venue: {venue.get('name', 'N/A')}")
                            print(f"Address: {venue.get('address', {}).get('localized_address_display', 'N/A')}")
            except Exception as e:
                print(f"Error: {e}")
