#!/usr/bin/env python3
"""
Test script to explore Venice West events page structure.
"""
import requests
from bs4 import BeautifulSoup

def explore_venice_west():
    """Explore Venice West events page structure."""
    url = "https://www.thevenicewest.com/calendar"

    print(f"Fetching: {url}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}\n")

    if response.status_code != 200:
        print("Failed to fetch page")
        return

    soup = BeautifulSoup(response.text, 'lxml')

    print("="*80)
    print("PAGE STRUCTURE ANALYSIS")
    print("="*80)

    # Look for event containers
    print("\n1. Looking for event containers...")

    # Try various selectors
    selectors_to_try = [
        ('div', {'class': 'event'}),
        ('div', {'class': 'event-item'}),
        ('div', {'class': 'calendar-item'}),
        ('div', {'class': 'event-card'}),
        ('article', None),
        ('div', {'data-event': True}),
        ('a', {'class': 'event'}),
    ]

    for tag, attrs in selectors_to_try:
        elements = soup.find_all(tag, attrs)
        if elements:
            print(f"   - {tag} {attrs}: {len(elements)} found")

    # Look for date/time elements
    print("\n2. Looking for date/time elements...")
    time_elements = soup.find_all('time')
    print(f"   Found {len(time_elements)} <time> elements")
    if time_elements:
        for i, elem in enumerate(time_elements[:3]):
            print(f"   Time {i+1}: {elem}")

    # Look for links
    print("\n3. Looking for event links...")
    links = soup.find_all('a', href=True)
    event_links = [l for l in links if 'tixr' in l.get('href', '') or 'event' in l.get('href', '').lower()]
    print(f"   Found {len(event_links)} event-related links")
    if event_links:
        for i, link in enumerate(event_links[:5]):
            print(f"   Link {i+1}: {link.get('href')} - Text: {link.get_text()[:50]}")

    # Look for headings that might be titles
    print("\n4. Looking for event titles (h1-h6)...")
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        headings = soup.find_all(tag)
        if headings:
            print(f"   Found {len(headings)} <{tag}> elements")
            if headings and len(headings) < 20:
                for i, h in enumerate(headings[:5]):
                    print(f"     {tag} {i+1}: {h.get_text()[:100]}")

    # Look for divs with specific classes
    print("\n5. Looking for common Webflow/calendar classes...")
    webflow_classes = [
        'w-dyn-item',
        'w-dyn-list',
        'collection-item',
        'collection-list',
        'calendar',
        'event-wrapper',
        'event-container'
    ]

    for class_name in webflow_classes:
        elements = soup.find_all(class_=class_name)
        if elements:
            print(f"   - .{class_name}: {len(elements)} found")

    # Check for all divs with class attributes
    print("\n6. All unique div classes (first 30)...")
    all_divs = soup.find_all('div', class_=True)
    all_classes = set()
    for div in all_divs:
        classes = div.get('class', [])
        if isinstance(classes, list):
            all_classes.update(classes)

    unique_classes = sorted(list(all_classes))[:30]
    for cls in unique_classes:
        print(f"   - {cls}")

    # Look for structured data
    print("\n7. Looking for structured data (JSON-LD)...")
    json_lds = soup.find_all('script', type='application/ld+json')
    print(f"   Found {len(json_lds)} JSON-LD scripts")
    if json_lds:
        import json
        for i, script in enumerate(json_lds):
            try:
                data = json.loads(script.string)
                print(f"   JSON-LD {i+1} type: {data.get('@type', 'Unknown')}")
            except:
                pass

    # Save HTML for inspection
    output_file = '/tmp/venicewest_calendar.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(response.text)
    print(f"\n8. Full HTML saved to: {output_file}")

    # Print a sample section of HTML
    print("\n9. Sample HTML (first 2000 chars of body)...")
    print("-" * 80)
    body = soup.find('body')
    if body:
        print(body.prettify()[:2000])
    print("-" * 80)

if __name__ == '__main__':
    explore_venice_west()
