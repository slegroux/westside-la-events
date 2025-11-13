#!/usr/bin/env python3
"""
Reclassify all events in the database using the updated category classifier.
This script updates events that were previously misclassified.
"""

from src.data.database import Database
from src.utils.categories import classify_event

def reclassify_all_events():
    """Reclassify all events in the database."""
    db = Database()

    # Get all events
    print("Fetching all events from database...")
    all_events = db.get_all_events()
    print(f"Found {len(all_events)} events")

    updated_count = 0
    unchanged_count = 0

    for i, event in enumerate(all_events, 1):
        # Get current category
        old_category = event.category

        # Reclassify using updated classifier
        new_category = classify_event(
            title=event.title,
            description=event.description or '',
            venue=event.venue_name or ''
        )

        # Update if category changed
        if old_category != new_category:
            print(f"[{i}/{len(all_events)}] Updating: {event.title}")
            print(f"  {old_category} -> {new_category}")
            print(f"  Venue: {event.venue_name}")

            # Update in database
            db.update_event_category(event.id, new_category)
            updated_count += 1
        else:
            unchanged_count += 1
            if i % 100 == 0:
                print(f"[{i}/{len(all_events)}] Processed {i} events ({updated_count} updated, {unchanged_count} unchanged)")

    print(f"\nReclassification complete!")
    print(f"Total events: {len(all_events)}")
    print(f"Updated: {updated_count}")
    print(f"Unchanged: {unchanged_count}")

if __name__ == '__main__':
    reclassify_all_events()
