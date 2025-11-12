#!/usr/bin/env python3
"""Analyze detail pages from each source to understand structure."""

import requests
from bs4 import BeautifulSoup
import time

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("="*80)
print("TIMEOUT LA - Detail Page Structure")
print("="*80)

# Sample Timeout event
timeout_url = "https://www.timeout.com/los-angeles/movies/rooftop-cinema-club"
r = requests.get(timeout_url, headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

print(f"\nURL: {timeout_url}\n")

# Find venue
venue = soup.find(class_=lambda x: x and 'venueName' in str(x))
print(f"Venue: {venue.get_text(strip=True) if venue else 'NOT FOUND'}")

# Find address
address_section = soup.find('section', class_=lambda x: x and 'venue' in str(x).lower())
if address_section:
    address_text = address_section.get_text(strip=True)
    print(f"Address section: {address_text[:200]}")

# Find description
desc_container = soup.find('div', class_=lambda x: x and 'body' in str(x).lower())
if desc_container:
    paragraphs = desc_container.find_all('p')
    if paragraphs:
        desc = paragraphs[0].get_text(strip=True)
        print(f"Description: {desc[:200]}...")

# Find image
meta_image = soup.find('meta', property='og:image')
if meta_image:
    print(f"Image: {meta_image.get('content', '')[:80]}...")

time.sleep(1)

print("\n" + "="*80)
print("KCRW - Detail Page Structure")
print("="*80)

# Sample KCRW event
kcrw_url = "https://www.kcrw.com/events/bardo-with-michael-seyer-and-pink-lemon"
r = requests.get(kcrw_url, headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

print(f"\nURL: {kcrw_url}\n")

# Find venue/location info
venue_info = soup.find('a', href=lambda x: x and '/venue/' in str(x))
if venue_info:
    print(f"Venue link: {venue_info.get_text(strip=True)}")
    print(f"Venue href: {venue_info.get('href')}")

# Look for address/location data
location_divs = soup.find_all(class_=lambda x: x and 'location' in str(x).lower())
for div in location_divs[:2]:
    print(f"Location element: {div.get_text(strip=True)[:100]}")

# Find description
desc = soup.find('div', class_=lambda x: x and 'description' in str(x).lower())
if desc:
    print(f"Description: {desc.get_text(strip=True)[:200]}...")

# Alternative: look for any paragraphs
if not desc:
    article = soup.find('article') or soup.find('main')
    if article:
        paragraphs = article.find_all('p')
        if paragraphs:
            print(f"First paragraph: {paragraphs[0].get_text(strip=True)[:200]}...")

# Image
meta_image = soup.find('meta', property='og:image')
if meta_image:
    print(f"Image: {meta_image.get('content', '')[:80]}...")

time.sleep(1)

print("\n" + "="*80)
print("DISCOVER LA - Detail Page Structure")
print("="*80)

# Get a sample Discover LA event
from src.data.database import Database
db = Database()
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT url FROM events WHERE source = 'Discover LA' AND url != '' LIMIT 1")
    row = cursor.fetchone()
    if row:
        discover_url = row[0]
        print(f"\nURL: {discover_url}\n")

        r = requests.get(discover_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Find venue
        venue = soup.find(class_=lambda x: x and 'venue' in str(x).lower())
        if venue:
            print(f"Venue: {venue.get_text(strip=True)[:100]}")

        # Find address
        address = soup.find('address') or soup.find(class_=lambda x: x and 'address' in str(x).lower())
        if address:
            print(f"Address: {address.get_text(strip=True)}")

        # Find description
        desc = soup.find(class_=lambda x: x and ('description' in str(x).lower() or 'content' in str(x).lower()))
        if desc:
            print(f"Description: {desc.get_text(strip=True)[:200]}...")

        # Image
        meta_image = soup.find('meta', property='og:image')
        if meta_image:
            print(f"Image: {meta_image.get('content', '')[:80]}...")
    else:
        print("No Discover LA events in database")

print("\n" + "="*80)
