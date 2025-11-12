#!/usr/bin/env python3
"""Deep dive into detail page structure."""

import requests
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

print("="*80)
print("TIMEOUT DETAIL PAGE - FULL VENUE SECTION")
print("="*80)

url = "https://www.timeout.com/los-angeles/movies/rooftop-cinema-club"
r = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

# Save HTML for inspection
with open('timeout_detail.html', 'w') as f:
    f.write(soup.prettify())
print("Saved to: timeout_detail.html")

# Find venue section
venue_sections = soup.find_all('section', class_=lambda x: x and 'venue' in str(x).lower())
print(f"\nFound {len(venue_sections)} venue sections\n")

for i, section in enumerate(venue_sections, 1):
    print(f"Venue Section {i}:")
    print(f"  Classes: {section.get('class')}")
    # Get all text
    all_text = section.get_text(separator='|', strip=True)
    print(f"  Text: {all_text[:300]}")

    # Look for links
    links = section.find_all('a')
    for link in links:
        print(f"  Link: {link.get_text(strip=True)} -> {link.get('href')}")

    # Look for address elements
    addresses = section.find_all('address')
    for addr in addresses:
        print(f"  Address: {addr.get_text(strip=True)}")
    print()

# Look for structured data (JSON-LD)
json_ld = soup.find('script', type='application/ld+json')
if json_ld:
    print("\nFound JSON-LD structured data:")
    import json
    try:
        data = json.loads(json_ld.string)
        print(json.dumps(data, indent=2)[:500])
    except:
        print(json_ld.string[:500])

print("\n" + "="*80)
print("KCRW DETAIL PAGE - FULL STRUCTURE")
print("="*80)

url = "https://www.kcrw.com/events/bardo-with-michael-seyer-and-pink-lemon"
r = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

with open('kcrw_detail.html', 'w') as f:
    f.write(soup.prettify())
print("Saved to: kcrw_detail.html")

# Find event details container
detail_sections = soup.find_all(class_=lambda x: x and ('detail' in str(x).lower() or 'info' in str(x).lower()))
print(f"\nFound {len(detail_sections)} detail/info sections\n")

for i, section in enumerate(detail_sections[:3], 1):
    print(f"Section {i}:")
    print(f"  Classes: {section.get('class')}")
    print(f"  Text: {section.get_text(strip=True)[:200]}")
    print()

# Look for venue/location specifically
venue_link = soup.find('a', href=lambda x: x and '/venue/' in str(x))
if venue_link:
    print(f"Venue link found: {venue_link.get_text(strip=True)}")
    print(f"Venue URL: https://www.kcrw.com{venue_link.get('href')}")

    # Could fetch venue page for full address
    venue_url = f"https://www.kcrw.com{venue_link.get('href')}"
    print(f"\nFetching venue page: {venue_url}")
    r_venue = requests.get(venue_url, headers=headers, timeout=10)
    soup_venue = BeautifulSoup(r_venue.text, 'html.parser')

    # Look for address on venue page
    address = soup_venue.find('address')
    if address:
        print(f"Venue address: {address.get_text(strip=True)}")

    # Look for any text that looks like an address
    all_text = soup_venue.get_text()
    import re
    # Look for street addresses
    addresses = re.findall(r'\d+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Road|Rd)', all_text)
    if addresses:
        print(f"Found addresses: {addresses[:3]}")

# Look for structured data
json_ld = soup.find('script', type='application/ld+json')
if json_ld:
    print("\nFound JSON-LD structured data:")
    import json
    try:
        data = json.loads(json_ld.string)
        print(json.dumps(data, indent=2)[:500])
    except:
        pass
