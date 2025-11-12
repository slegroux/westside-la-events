#!/usr/bin/env python3
"""Test KCRW parsing with actual HTML."""

from bs4 import BeautifulSoup

# Read the saved HTML
with open('debug_kcrw.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# Find all event cards
event_cards = soup.find_all('div', class_='EventCard_cardContainer__8MM5C')
print(f"Found {len(event_cards)} event cards\n")

# Parse first 3 events to understand structure
for i, card in enumerate(event_cards[:3], 1):
    print(f"{'='*60}")
    print(f"Event {i}")
    print(f"{'='*60}")

    # Date
    date_elem = card.find('div', class_='EventCard_date__Rr2V0')
    if date_elem:
        date_parts = [s.strip() for s in date_elem.stripped_strings]
        print(f"Date: {' '.join(date_parts)}")

    # Title
    title_elem = card.find('p', class_='EventCard_cardTitle__quf8x')
    if title_elem:
        title = title_elem.get_text(strip=True)
        print(f"Title: {title}")

    # Venue
    venue_elem = card.find('p', class_='small-text')
    if venue_elem:
        venue = venue_elem.get_text(strip=True)
        print(f"Venue: {venue}")

    # Category/Tags
    tags = card.find_all('div', class_='Tag_tag__A2jv3')
    if tags:
        tag_texts = [tag.get_text(strip=True) for tag in tags]
        print(f"Tags: {', '.join(tag_texts)}")

    # URL - need to find parent link
    # Look for an <a> tag that contains this card
    parent_link = card.find_parent('a')
    if parent_link and parent_link.get('href'):
        print(f"URL: {parent_link['href']}")

    # Image
    img = card.find('img')
    if img:
        img_src = img.get('src', '')
        print(f"Image: {img_src[:80]}...")

    print()
