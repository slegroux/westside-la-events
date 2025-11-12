#!/usr/bin/env python3
"""Analyze Meetup structure for scraping."""

import requests
from bs4 import BeautifulSoup
import json

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Try Meetup search for Los Angeles
url = "https://www.meetup.com/find/?location=us--ca--los-angeles&source=EVENTS"
print(f"Fetching: {url}\n")

try:
    r = requests.get(url, headers=headers, timeout=10)
    print(f"Status code: {r.status_code}\n")

    soup = BeautifulSoup(r.text, 'html.parser')

    # Save HTML for analysis
    with open('meetup_listing.html', 'w') as f:
        f.write(soup.prettify())
    print("Saved HTML to: meetup_listing.html\n")

    print("="*80)
    print("MEETUP LISTING PAGE STRUCTURE")
    print("="*80)

    # Look for event cards
    print("\nSearching for event containers...")

    # Common patterns
    patterns = ['event', 'card', 'result', 'search']

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
            print(f"Type: {data.get('@type')}")
            if isinstance(data, list):
                print(f"List with {len(data)} items")
                if data:
                    print(f"First item type: {data[0].get('@type')}")
            print(json.dumps(data, indent=2)[:500])
        except Exception as e:
            print(f"Failed to parse: {e}")

    # Look for Next.js data
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        print("\n\n=== NEXT.JS DATA FOUND ===")
        try:
            data = json.loads(next_data.string)
            print("Top-level keys:", list(data.keys())[:10])
            if 'props' in data:
                print("Props keys:", list(data['props'].keys())[:10])
                if 'pageProps' in data['props']:
                    page_props = data['props']['pageProps']
                    print("PageProps keys:", list(page_props.keys())[:10])
                    # Look for events data
                    if 'searchResults' in page_props:
                        results = page_props['searchResults']
                        print(f"\nFound searchResults with keys: {list(results.keys())}")
                        if 'edges' in results:
                            print(f"Number of events: {len(results['edges'])}")
                            if results['edges']:
                                first_event = results['edges'][0]
                                print("\nFirst event structure:")
                                print(json.dumps(first_event, indent=2)[:800])
        except Exception as e:
            print(f"Error parsing Next.js data: {e}")

    # Look for API calls in scripts
    print("\n\n=== CHECKING FOR API ENDPOINTS ===")
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and ('api' in script.string.lower() or 'graphql' in script.string.lower()):
            # Look for URLs
            import re
            urls = re.findall(r'https?://[^\s"\'<>]+', script.string)
            if urls:
                print("Found API-related URLs:")
                for url in urls[:5]:
                    if 'api' in url or 'graphql' in url:
                        print(f"  {url}")
                break

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Also try direct event search URL
print("\n\n" + "="*80)
print("TRYING ALTERNATIVE MEETUP URL")
print("="*80)

try:
    alt_url = "https://www.meetup.com/find/events/?location=us--ca--los-angeles"
    print(f"\nFetching: {alt_url}")
    r = requests.get(alt_url, headers=headers, timeout=10)
    print(f"Status code: {r.status_code}")
    print(f"Page size: {len(r.text)} bytes")

    # Check if it redirects or has content
    if 'event' in r.text.lower():
        print("✓ Page contains 'event' keyword")
    if 'json' in r.text.lower():
        print("✓ Page contains 'json' keyword (likely has structured data)")

except Exception as e:
    print(f"Error with alternative URL: {e}")
