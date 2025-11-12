#!/usr/bin/env python3
"""
Clean up existing duplicate events in the database.

This script will:
1. Find all duplicate events
2. Merge data from duplicates into the primary event
3. Delete the duplicate entries
"""
import sqlite3
from datetime import datetime
from collections import defaultdict

from src.data.database import Database
from src.data.models import Event
from src.utils.deduplication import events_are_duplicates, merge_event_data


def cleanup_duplicates(db_path='./data/events.db', dry_run=True):
    """
    Clean up duplicate events in the database.

    Args:
        db_path: Path to database file
        dry_run: If True, only show what would be done without actually deleting
    """
    db = Database(db_path)

    print(f"{'='*80}")
    print(f"DUPLICATE CLEANUP {'(DRY RUN)' if dry_run else '(LIVE)'}")
    print(f"{'='*80}\n")

    # Get all events
    all_events = db.get_all_events(limit=10000)
    print(f"Total events in database: {len(all_events)}\n")

    # Group events by date to reduce comparisons
    events_by_date = defaultdict(list)
    for event in all_events:
        if event.event_date:
            date_key = event.event_date.date().isoformat()
            events_by_date[date_key].append(event)

    # Find duplicates
    duplicate_groups = []
    processed_ids = set()

    for date, date_events in sorted(events_by_date.items()):
        for i, event1 in enumerate(date_events):
            if event1.id in processed_ids:
                continue

            group = [event1]

            for event2 in date_events[i+1:]:
                if event2.id in processed_ids:
                    continue

                is_dup, scores = events_are_duplicates(event1, event2)
                if is_dup:
                    group.append(event2)
                    processed_ids.add(event2.id)

            if len(group) > 1:
                processed_ids.add(event1.id)
                duplicate_groups.append(group)

    print(f"Found {len(duplicate_groups)} duplicate groups\n")

    if len(duplicate_groups) == 0:
        print("✓ No duplicates found!")
        return

    # Process each duplicate group
    total_deleted = 0

    for idx, group in enumerate(duplicate_groups, 1):
        print(f"\n{'─'*80}")
        print(f"GROUP #{idx}")
        print(f"{'─'*80}")

        # Choose primary event (prefer earliest created_at)
        group.sort(key=lambda e: e.created_at if e.created_at else datetime.max)
        primary = group[0]

        print(f"\nPrimary Event (ID: {primary.id}, Source: {primary.source}):")
        print(f"  Title: {primary.title}")
        print(f"  Venue: {primary.venue_name}")
        print(f"  Date: {primary.event_date}")

        print(f"\nDuplicates to merge:")
        for dup in group[1:]:
            print(f"  - ID: {dup.id}, Source: {dup.source}")

        # Merge all duplicates into primary
        merged = primary
        for dup in group[1:]:
            merged = merge_event_data(merged, dup)

        # Update primary with merged data
        if not dry_run:
            db.update_event(merged)
            print(f"\n✓ Updated primary event with merged data")

            # Delete duplicates
            for dup in group[1:]:
                db.delete_event(dup.id)
                total_deleted += 1
                print(f"  ✓ Deleted duplicate ID {dup.id}")
        else:
            print(f"\n  [DRY RUN] Would update event {primary.id}")
            for dup in group[1:]:
                print(f"  [DRY RUN] Would delete event {dup.id}")

    print(f"\n\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Events to delete: {total_deleted}")
    print(f"Final event count: {len(all_events) - total_deleted}")

    if dry_run:
        print(f"\n⚠ This was a DRY RUN. No changes were made.")
        print(f"Run with --live to actually clean up duplicates.")
    else:
        print(f"\n✓ Cleanup complete!")


if __name__ == '__main__':
    import sys

    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--live':
        response = input("This will permanently delete duplicate events. Are you sure? (yes/no): ")
        if response.lower() == 'yes':
            dry_run = False
        else:
            print("Cancelled.")
            sys.exit(0)

    cleanup_duplicates(dry_run=dry_run)
