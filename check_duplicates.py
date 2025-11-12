#!/usr/bin/env python3
"""
Check for duplicate events from different sources in the database.
"""
import sqlite3
from datetime import datetime
from collections import defaultdict
from difflib import SequenceMatcher

def similar(a, b):
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def check_duplicates(db_path='./data/events.db', similarity_threshold=0.85):
    """
    Check for duplicate events from different sources.

    Args:
        db_path: Path to SQLite database
        similarity_threshold: Minimum similarity ratio to consider duplicates (0-1)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all events
    cursor.execute("""
        SELECT id, title, venue_name, address, event_date, source, url
        FROM events
        ORDER BY event_date, title
    """)

    events = [dict(row) for row in cursor.fetchall()]

    print(f"\n{'='*80}")
    print(f"DUPLICATE EVENT ANALYSIS")
    print(f"{'='*80}")
    print(f"Total events in database: {len(events)}")
    print(f"Similarity threshold: {similarity_threshold}")
    print(f"{'='*80}\n")

    # Group events by date to reduce comparisons
    events_by_date = defaultdict(list)
    for event in events:
        date = event['event_date'][:10] if event['event_date'] else 'no_date'
        events_by_date[date].append(event)

    duplicate_groups = []
    processed_ids = set()

    # Check for duplicates within each date
    for date, date_events in sorted(events_by_date.items()):
        for i, event1 in enumerate(date_events):
            if event1['id'] in processed_ids:
                continue

            duplicates = [event1]

            for event2 in date_events[i+1:]:
                if event2['id'] in processed_ids:
                    continue

                # Skip if same source
                if event1['source'] == event2['source']:
                    continue

                # Check title similarity
                title_sim = similar(event1['title'], event2['title'])
                venue_sim = similar(event1['venue_name'] or '', event2['venue_name'] or '')

                # Consider duplicates if titles are very similar OR
                # titles are somewhat similar AND venues match
                if title_sim >= similarity_threshold or \
                   (title_sim >= 0.7 and venue_sim >= 0.8):
                    duplicates.append(event2)
                    processed_ids.add(event2['id'])

            if len(duplicates) > 1:
                processed_ids.add(event1['id'])
                duplicate_groups.append(duplicates)

    # Print results
    print(f"Found {len(duplicate_groups)} groups of potential duplicates\n")

    for idx, group in enumerate(duplicate_groups, 1):
        print(f"\n{'─'*80}")
        print(f"DUPLICATE GROUP #{idx}")
        print(f"{'─'*80}")

        for event in group:
            print(f"\nID: {event['id']}")
            print(f"Title: {event['title']}")
            print(f"Venue: {event['venue_name']}")
            print(f"Address: {event['address']}")
            print(f"Date: {event['event_date']}")
            print(f"Source: {event['source']}")
            print(f"URL: {event['url']}")

        # Show similarity scores
        if len(group) == 2:
            title_sim = similar(group[0]['title'], group[1]['title'])
            venue_sim = similar(group[0]['venue_name'] or '', group[1]['venue_name'] or '')
            print(f"\nSimilarity Scores:")
            print(f"  Title: {title_sim:.2%}")
            print(f"  Venue: {venue_sim:.2%}")

    # Summary statistics
    print(f"\n\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")

    # Count events by source
    source_counts = defaultdict(int)
    for event in events:
        source_counts[event['source']] += 1

    print(f"\nEvents by source:")
    for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {source}: {count}")

    # Duplicate statistics
    total_duplicates = sum(len(group) for group in duplicate_groups)
    unique_events = len(events) - total_duplicates + len(duplicate_groups)

    print(f"\nDuplicate statistics:")
    print(f"  Total events: {len(events)}")
    print(f"  Duplicate groups: {len(duplicate_groups)}")
    print(f"  Total duplicate events: {total_duplicates}")
    print(f"  Estimated unique events: {unique_events}")
    print(f"  Duplication rate: {(total_duplicates / len(events) * 100):.1f}%")

    conn.close()

    return duplicate_groups

if __name__ == '__main__':
    import sys

    threshold = 0.85
    if len(sys.argv) > 1:
        try:
            threshold = float(sys.argv[1])
        except ValueError:
            print(f"Invalid threshold: {sys.argv[1]}")
            sys.exit(1)

    check_duplicates(similarity_threshold=threshold)
