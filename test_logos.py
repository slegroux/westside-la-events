"""
Test script to verify source logos are being scraped and displayed correctly.
"""
from src.utils.logo_scraper import LogoScraper


def main():
    """Test logo scraping for all sources."""
    print("=" * 60)
    print("Testing Source Logo Scraping")
    print("=" * 60)

    scraper = LogoScraper()

    # Get all logos
    logos = scraper.get_all_logos()

    if not logos:
        print("\nNo logos found!")
        return

    print(f"\nFound logos for {len(logos)} sources:\n")

    for source, logo_url in logos.items():
        print(f"✓ {source}")
        print(f"  URL: {logo_url}")
        print()

    print("=" * 60)
    print("Testing Logo Downloads")
    print("=" * 60)

    for source in scraper.SOURCE_URLS.keys():
        print(f"\nDownloading logo for: {source}")
        local_path = scraper.download_logo(source)

        if local_path:
            print(f"  ✓ Downloaded to: {local_path}")
        else:
            print(f"  ✗ Failed to download")

    print("\n" + "=" * 60)
    print("Logo scraping test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
