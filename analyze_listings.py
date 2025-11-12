#!/usr/bin/env python3
"""Analyze what data is available in listing pages vs detail pages."""

import requests
from bs4 import BeautifulSoup

print("="*80)
print("TIMEOUT LA - Listing Page Analysis")
print("="*80)

url = "https://www.timeout.com/los-angeles/things-to-do/things-to-do-in-los-angeles-today"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

response = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

# Find first event card
card = soup.find('article', class_='tile')
if card:
    print("\n First Event Card:")
    print(f"  Title: {card.find('h3', {'data-testid': 'tile-title_testID'}).get_text() if card.find('h3', {'data-testid': 'tile-title_testID'}) else 'None'}")

    # Description
    desc = card.find('p')
    print(f"  Description snippet: {desc.get_text()[:100] if desc else 'None'}...")

    # Tags
    tags_section = card.find('section', {'data-testid': 'tags_testID'})
    if tags_section:
        tags = [li.get_text(strip=True) for li in tags_section.find_all('li')]
        print(f"  Tags: {tags}")

    # Link
    link = card.find('a', {'data-testid': 'tile-link_testID'})
    if link:
        detail_url = 'https://www.timeout.com' + link['href']
        print(f"\n  Detail URL: {detail_url}")

        # Fetch detail page
        print("\n  Fetching detail page...")
        detail_response = requests.get(detail_url, headers=headers, timeout=10)
        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

        # Venue
        venue = detail_soup.find(class_='_venueName_1uzv8_47')
        print(f"    Venue: {venue.get_text(strip=True) if venue else 'None'}")

        # Full description
        body = detail_soup.find('div', class_=lambda x: x and 'body' in str(x).lower())
        if body:
            full_desc = body.get_text(strip=True)
            print(f"    Full description: {full_desc[:200]}...")

        # Address
        address = detail_soup.find('address')
        print(f"    Address: {address.get_text(strip=True) if address else 'None'}")

print("\n")
print("="*80)
print("KCRW - Listing Page Analysis")
print("="*80)

kcrw_url = "https://www.kcrw.com/events"
response = requests.get(kcrw_url, headers=headers, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

card = soup.find('div', class_=lambda x: x and 'EventCard_cardContainer__' in x)
if card:
    print("\nFirst Event Card:")
    title = card.find('p', class_=lambda x: x and 'EventCard_cardTitle__' in x)
    print(f"  Title: {title.get_text(strip=True) if title else 'None'}")

    venue = card.find('p', class_='small-text')
    print(f"  Venue (listing): {venue.get_text(strip=True) if venue else 'None'}")

    # Get detail URL
    parent_link = card.find_parent('a')
    if parent_link:
        detail_url = 'https://www.kcrw.com' + parent_link['href']
        print(f"\n  Detail URL: {detail_url}")

        # Fetch detail
        print("\n  Fetching detail page...")
        detail_response = requests.get(detail_url, headers=headers, timeout=10)
        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

        # Look for description
        desc = detail_soup.find('div', class_=lambda x: x and 'description' in str(x).lower())
        if desc:
            print(f"    Description: {desc.get_text(strip=True)[:200]}...")

        # Look for venue details
        venue_detail = detail_soup.find('h3', string=lambda x: x and 'venue' in str(x).lower())
        if venue_detail:
            venue_info = venue_detail.find_next('p')
            if venue_info:
                print(f"    Venue detail: {venue_info.get_text(strip=True)}")
