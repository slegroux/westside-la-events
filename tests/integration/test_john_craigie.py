"""Quick test for the specific John Craigie event URL."""
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time

def test_specific_url():
    """Test the John Craigie event page."""
    url = "https://www.tixr.com/groups/thevenicewest/events/john-craigie-w-special-guest-the-coffis-brothers-135940"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        print(f"Loading: {url}")
        try:
            response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
            print(f"Response status: {response.status}")

            # Wait for page to load
            time.sleep(5)

            # Check for anti-bot protection
            content = page.content()
            if 'datadome' in content.lower() or 'captcha' in content.lower():
                print("\n❌ BLOCKED: Anti-bot protection detected!")
                print("DataDome or CAPTCHA is blocking access")

            # Try to find price elements
            print("\n=== Looking for price information ===")

            # Look for any text with dollar signs
            page.wait_for_timeout(2000)

            # Try to get text from the page
            text = page.inner_text('body')

            # Search for dollar amounts
            dollar_matches = re.findall(r'\$\s*(\d+(?:\.\d{2})?)', text)
            if dollar_matches:
                print(f"\n✓ Found prices: {dollar_matches}")
            else:
                print("\n✗ No prices found in page text")

            # Save screenshot
            page.screenshot(path='/tmp/tixr_screenshot.png')
            print("\nSaved screenshot to /tmp/tixr_screenshot.png")

            # Save HTML
            with open('/tmp/tixr_page.html', 'w', encoding='utf-8') as f:
                f.write(content)
            print("Saved HTML to /tmp/tixr_page.html")

            time.sleep(5)  # Give time to see the browser

        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            browser.close()

if __name__ == '__main__':
    test_specific_url()
