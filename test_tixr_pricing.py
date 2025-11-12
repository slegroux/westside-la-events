"""Test script to extract pricing from Tixr event pages."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def test_tixr_pricing():
    """Test extracting pricing from a Tixr event page."""
    url = "https://www.tixr.com/groups/thevenicewest/events/cubensis-tribute-to-grateful-dead-157931"

    with sync_playwright() as p:
        # Use more realistic browser setup
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # Remove webdriver property
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print(f"Loading: {url}")
        page.goto(url, wait_until='domcontentloaded', timeout=60000)

        # Wait for pricing/ticket elements to load
        # Try waiting for various possible selectors
        try:
            page.wait_for_selector('text=GA', timeout=10000)
        except:
            pass

        # Wait a bit more for dynamic content
        page.wait_for_timeout(5000)

        # Get HTML
        html = page.content()
        browser.close()

        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # Save HTML for inspection
        with open('/tmp/tixr_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Saved HTML to /tmp/tixr_page.html")

        # Look for price information
        # Try to find ticket types and prices
        print("\n=== Looking for pricing information ===\n")

        # Search for dollar signs in text
        dollar_texts = soup.find_all(string=re.compile(r'\$\d+'))
        print(f"Found {len(dollar_texts)} elements with dollar amounts:")
        for i, text in enumerate(dollar_texts[:10], 1):
            parent = text.parent
            print(f"{i}. '{text.strip()}' in <{parent.name} class={parent.get('class')}>")

        # Look for common ticket/pricing class names
        print("\n=== Looking for ticket elements ===\n")
        ticket_keywords = ['ticket', 'price', 'admission', 'tier', 'level', 'option']
        for keyword in ticket_keywords:
            elements = soup.find_all(class_=re.compile(keyword, re.I))
            if elements:
                print(f"\nFound {len(elements)} elements with '{keyword}' in class:")
                for elem in elements[:3]:
                    print(f"  <{elem.name} class={elem.get('class')}>")
                    print(f"    Text: {elem.get_text(strip=True)[:100]}")

if __name__ == '__main__':
    test_tixr_pricing()
