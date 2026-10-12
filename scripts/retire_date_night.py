#!/usr/bin/env python3
"""
Retire the 'Date Night' category from stored events.

Date night is a mood, not an event type, so it is now a curated view (the hero
"Date night" chip) rather than a category. The classifier no longer produces
it; this re-runs the classifier on the rows still labelled 'Date Night' so they
land in a real category (the weekly jazz nights go back to Music). The scraper
runs the same step after every scrape, so this is only needed for a database
that won't be scraped.

Usage: python scripts/retire_date_night.py [path/to/events.db]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from src.data.database import Database
from src.utils.categories import reclassify_retired


if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else config.DATABASE_PATH
    moved = reclassify_retired(Database(db_path))
    print(f"Reclassified {sum(moved.values())} 'Date Night' events in {db_path}")
    for category, count in moved.most_common():
        print(f"  {category}: {count}")
