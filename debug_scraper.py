#!/usr/bin/env python3
"""Debug script to inspect HTML structure of event pages."""

import requests
from bs4 import BeautifulSoup

def inspect_site(name, url):
    """Fetch and display HTML structure of a site."""
    print(f"\n{'='*60}")
    print(f"{name}: {url}")
    print(f"{'='*60}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Save full HTML to file for inspection
        filename = f"debug_{name.lower().replace(' ', '_')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print(f"✓ Saved HTML to: {filename}")

        # Look for common event container patterns
        print("\nSearching for event containers...")

        # Check for common class patterns
        patterns = [
            'event', 'card', 'item', 'listing', 'article',
            'post', 'entry', 'content', 'tile', 'box'
        ]

        for pattern in patterns:
            # Find elements with class containing pattern
            elements = soup.find_all(class_=lambda x: x and pattern in x.lower())
            if elements:
                unique_classes = set()
                for elem in elements[:10]:  # Limit to first 10
                    if elem.get('class'):
                        unique_classes.update(elem['class'])
                if unique_classes:
                    print(f"\n  Classes containing '{pattern}': {len(elements)} elements found")
                    for cls in sorted(unique_classes)[:5]:  # Show first 5
                        print(f"    - {cls}")

        # Check for script tags (might be loading data via JS)
        scripts = soup.find_all('script', src=True)
        print(f"\n  Found {len(scripts)} external scripts")

        # Check for data attributes or JSON
        json_scripts = soup.find_all('script', type='application/json')
        ld_json_scripts = soup.find_all('script', type='application/ld+json')
        print(f"  Found {len(json_scripts)} JSON scripts")
        print(f"  Found {len(ld_json_scripts)} JSON-LD scripts")

        # Look for specific elements
        h1s = soup.find_all('h1')
        h2s = soup.find_all('h2')
        h3s = soup.find_all('h3')
        print(f"\n  Headers: {len(h1s)} h1, {len(h2s)} h2, {len(h3s)} h3")

        if h2s:
            print(f"  First 3 h2 texts:")
            for h2 in h2s[:3]:
                text = h2.get_text().strip()[:60]
                print(f"    - {text}...")

    except Exception as e:
        print(f"✗ Error: {e}")

def main():
    """Inspect both sites."""
    sites = [
        ("Santa Monica", "https://www.smgov.net/events"),
        ("KCRW", "https://www.kcrw.com/events"),
    ]

    for name, url in sites:
        inspect_site(name, url)

if __name__ == '__main__':
    main()
