#!/usr/bin/env python3
"""Test fetching Timeout event detail page."""

import requests
from bs4 import BeautifulSoup

def main():
    # Get a sample event URL from database
    from src.data.database import Database
    db = Database()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM events WHERE source = 'Timeout LA' AND url != '' LIMIT 1")
        row = cursor.fetchone()
        if row:
            url = row[0]
            print(f"Fetching detail page: {url}\n")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Look for venue information
            print("=== VENUE INFO ===")
            venue_sections = soup.find_all(class_=lambda x: x and 'venue' in x.lower())
            for section in venue_sections[:3]:
                print(f"Class: {section.get('class')}")
                print(f"Text: {section.get_text(strip=True)[:100]}\n")

            # Look for description
            print("\n=== DESCRIPTION ===")
            # Common description selectors
            desc = (soup.find('div', class_='body-text') or
                   soup.find('div', class_='description') or
                   soup.find('article'))
            if desc:
                print(desc.get_text(strip=True)[:300])

            # Look for address
            print("\n=== ADDRESS ===")
            address_elem = soup.find('address') or soup.find(class_=lambda x: x and 'address' in str(x).lower())
            if address_elem:
                print(address_elem.get_text(strip=True))
        else:
            print("No Timeout LA events found in database")

if __name__ == '__main__':
    main()
