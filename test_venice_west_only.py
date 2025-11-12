"""Quick test for Venice West scraper pricing improvements."""
from src.scrapers.venice_west import VeniceWestScraper
from src.data.database import Database

# Initialize scraper and database
scraper = VeniceWestScraper()
db = Database()

# Scrape events
print("Scraping Venice West events...")
events = scraper.scrape()

print(f"\nFound {len(events)} events\n")

# Display pricing information for each event
for i, event in enumerate(events, 1):
    print(f"{i}. {event.title}")
    print(f"   URL: {event.url}")
    if event.is_free:
        print(f"   Price: FREE")
    elif event.price:
        print(f"   Price: ${event.price:.2f}")
    elif event.price_note:
        print(f"   Price Note: {event.price_note}")
    else:
        print(f"   Price: Not available")
    print()

# Save to database
print(f"Saving events to database...")
saved_count = 0
skipped_count = 0

for event in events:
    event_id, was_duplicate = db.insert_event(event)
    if was_duplicate:
        skipped_count += 1
    else:
        saved_count += 1

print(f"✓ Saved {saved_count} new events")
print(f"✓ Skipped {skipped_count} duplicates")
