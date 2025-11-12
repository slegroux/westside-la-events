#!/usr/bin/env python3
"""
Reclassify all events in the database using the updated weighted category classifier.
"""
from src.data.database import Database
from src.utils.categories import classify_event

def main():
    # Connect to database
    db = Database('data/events.db')

    # Track changes
    reclassified = []
    date_night_count = 0
    category_counts = {}

    # Get all events and update them
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, description, venue_name, category FROM events')
        events = cursor.fetchall()

        print(f'Found {len(events)} total events')

        for event in events:
            event_id = event['id']
            title = event['title']
            description = event['description']
            venue_name = event['venue_name']
            old_category = event['category']

            # Classify with new weighted system
            new_category = classify_event(title, description or '', venue_name or '')

            # Count categories
            category_counts[new_category] = category_counts.get(new_category, 0) + 1

            if new_category != old_category:
                # Update the event
                cursor.execute(
                    'UPDATE events SET category = ? WHERE id = ?',
                    (new_category, event_id)
                )
                reclassified.append((title, old_category, new_category))

            if new_category == 'Date Night':
                date_night_count += 1

    print(f'\n✅ Reclassified {len(reclassified)} events')
    print(f'📅 Total Date Night events: {date_night_count}')

    print(f'\n📊 Category distribution:')
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f'   {category:20} {count:4} events')

    if len(reclassified) > 0:
        print(f'\n🔄 Sample reclassified events (showing first 30):')
        for title, old, new in reclassified[:30]:
            print(f'   • {title[:55]:<55} | {old:15} → {new}')

if __name__ == '__main__':
    main()
