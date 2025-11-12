#!/usr/bin/env python3
"""
Test script to explore LA Weekly events page structure.
"""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

def explore_laweekly():
    """Explore LA Weekly events page structure."""
    url = "https://www.laweekly.com/events/"

    print(f"Fetching: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Set user agent
        page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        # Navigate to page
        print("Loading page...")
        page.goto(url, wait_until='networkidle', timeout=60000)

        # Wait a bit for any dynamic content
        time.sleep(3)

        # Get HTML
        html = page.content()
        browser.close()

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        print("\n" + "="*80)
        print("PAGE STRUCTURE ANALYSIS")
        print("="*80)

        # Look for event listings
        print("\n1. Looking for event articles/cards...")
        articles = soup.find_all('article')
        print(f"   Found {len(articles)} <article> elements")

        # Look for event containers
        event_divs = soup.find_all('div', class_=lambda x: x and ('event' in x.lower() if isinstance(x, str) else False))
        print(f"   Found {len(event_divs)} divs with 'event' in class name")

        # Check for structured data
        print("\n2. Looking for structured data (JSON-LD)...")
        json_lds = soup.find_all('script', type='application/ld+json')
        print(f"   Found {len(json_lds)} JSON-LD scripts")

        # Look for common event listing patterns
        print("\n3. Common event listing selectors:")
        selectors_to_try = [
            ('article', None),
            ('div', {'class': 'event'}),
            ('div', {'class': 'event-item'}),
            ('div', {'class': 'event-card'}),
            ('li', {'class': 'event'}),
            ('section', None),
        ]

        for tag, attrs in selectors_to_try:
            elements = soup.find_all(tag, attrs)
            if elements:
                print(f"   - {tag} {attrs}: {len(elements)} found")

        # Print first article/event structure if found
        if articles:
            print("\n4. First article structure:")
            print("-" * 80)
            print(articles[0].prettify()[:1500])
            print("-" * 80)

        # Look for event titles
        print("\n5. Looking for event titles...")
        h2_titles = soup.find_all('h2')
        h3_titles = soup.find_all('h3')
        print(f"   Found {len(h2_titles)} <h2> elements")
        print(f"   Found {len(h3_titles)} <h3> elements")

        if h2_titles:
            print(f"\n   First h2 title: {h2_titles[0].get_text()[:100]}")
        if h3_titles:
            print(f"   First h3 title: {h3_titles[0].get_text()[:100]}")

        # Look for dates
        print("\n6. Looking for date/time elements...")
        time_elements = soup.find_all('time')
        print(f"   Found {len(time_elements)} <time> elements")
        if time_elements:
            print(f"   First time element: {time_elements[0]}")

        # Check main content area
        print("\n7. Main content containers:")
        main = soup.find('main')
        if main:
            print("   Found <main> element")
            # Look for children
            direct_children = list(main.children)
            print(f"   Main has {len(direct_children)} direct children")

        # Save HTML for manual inspection
        output_file = '/tmp/laweekly_events.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n8. Full HTML saved to: {output_file}")
        print("   You can open this file in a browser to inspect the structure")

if __name__ == '__main__':
    explore_laweekly()
