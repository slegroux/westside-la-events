#!/usr/bin/env python3
"""Test fetching Santa Monica page with JavaScript rendering."""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def main():
    url = "https://www.smgov.net/events"

    print(f"Fetching {url} with JavaScript rendering...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Use load instead of networkidle, which is more forgiving
        page.goto(url, wait_until='load', timeout=60000)

        # Wait for dynamic content to load
        page.wait_for_timeout(5000)

        html = page.content()
        browser.close()

    # Save HTML
    with open('debug_santa_monica_js.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ Saved HTML to: debug_santa_monica_js.html")

    # Parse and analyze
    soup = BeautifulSoup(html, 'html.parser')

    print("\nSearching for event containers...")

    # Look for common patterns
    patterns = ['event', 'card', 'item', 'listing']

    for pattern in patterns:
        elements = soup.find_all(class_=lambda x: x and pattern in x.lower())
        if elements:
            unique_classes = set()
            for elem in elements[:10]:
                if elem.get('class'):
                    unique_classes.update(elem['class'])
            if unique_classes:
                print(f"\n  Classes containing '{pattern}': {len(elements)} elements")
                for cls in sorted(unique_classes)[:10]:
                    print(f"    - {cls}")

    # Check for h1, h2, h3
    h2s = soup.find_all('h2')
    h3s = soup.find_all('h3')
    print(f"\n  Headers: {len(h2s)} h2, {len(h3s)} h3")

    if h2s:
        print(f"\n  First 5 h2 texts:")
        for h2 in h2s[:5]:
            text = h2.get_text().strip()[:60]
            print(f"    - {text}...")

if __name__ == '__main__':
    main()
