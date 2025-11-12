"""Test script to verify Venice West scraper can extract Tixr pricing."""
import sys
sys.path.insert(0, '/home/sylvain/Projects/LA')

from src.scrapers.venice_west import VeniceWestScraper

def test_venice_west_pricing():
    """Test the Venice West scraper pricing extraction."""
    scraper = VeniceWestScraper()

    print("Testing Tixr pricing extraction...")
    print("=" * 60)

    # Test with the Cubensis event
    test_url = "https://www.tixr.com/groups/thevenicewest/events/cubensis-tribute-to-grateful-dead-157931"
    print(f"\nTesting URL: {test_url}")
    print("-" * 60)

    # First, let's see what HTML we're getting
    html = scraper.fetch_page_js(test_url, timeout=45000)
    if html:
        with open('/tmp/tixr_venice_west.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Saved HTML to /tmp/tixr_venice_west.html")
        print(f"HTML length: {len(html)} characters")

        # Check for anti-bot
        if 'captcha' in html.lower() or 'datadome' in html.lower():
            print("WARNING: Anti-bot protection detected!")

    pricing_info = scraper._extract_tixr_pricing(test_url)

    print(f"\nResults:")
    print(f"  Min Price: ${pricing_info['min_price']}" if pricing_info['min_price'] else "  Min Price: Not found")
    print(f"  Max Price: ${pricing_info['max_price']}" if pricing_info['max_price'] else "  Max Price: Not found")
    print(f"  Price Tiers: {len(pricing_info['price_tiers'])} found")

    if pricing_info['price_tiers']:
        print("\n  Tiers:")
        for tier in pricing_info['price_tiers']:
            print(f"    - {tier['name']}: ${tier['price']}")

    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == '__main__':
    test_venice_west_pricing()
