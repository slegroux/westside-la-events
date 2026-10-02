#!/usr/bin/env python3
"""
Retire the 'Date Night' category from stored events.

Date night is a mood, not an event type, so it is now a curated view (the hero
"Date night" chip) rather than a category. The classifier no longer produces
it; this re-runs the classifier on the rows still labelled 'Date Night' so they
land in a real category (the weekly jazz nights go back to Music).

Usage: python scripts/retire_date_night.py [path/to/events.db]
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.data.database import Database
from src.utils.categories import classify_event

RETIRED = 'Date Night'


def reclassify_date_night(db: Database) -> Counter:
    """Reclassify every 'Date Night' row; return a count per new category."""
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, description, venue_name FROM events WHERE category = ?",
            (RETIRED,),
        ).fetchall()
        moved = Counter()
        for event_id, title, description, venue in rows:
            new_category = classify_event(title or '', description or '', venue or '')
            conn.execute(
                "UPDATE events SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_category, event_id),
            )
            moved[new_category] += 1
    return moved


if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else config.DATABASE_PATH
    moved = reclassify_date_night(Database(db_path))
    print(f"Reclassified {sum(moved.values())} '{RETIRED}' events in {db_path}")
    for category, count in moved.most_common():
        print(f"  {category}: {count}")
