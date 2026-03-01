#!/usr/bin/env python3
"""
Script to run all event scrapers and populate the database.
"""
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import config
from src.data.database import Database
from src.scrapers.registry import instantiate_enabled_scrapers

# Thread-local storage for database connections
thread_local = threading.local()


def get_thread_db():
    """Get or create a database connection for the current thread."""
    if not hasattr(thread_local, "db"):
        thread_local.db = Database(config.DATABASE_PATH)
    return thread_local.db


def run_scraper(scraper):
    """
    Run a scraper and save events to database.
    Thread-safe version that uses thread-local database connections.

    Args:
        scraper: Scraper instance

    Returns:
        dict: Summary of scraping results
    """
    # Get thread-local database connection
    db = get_thread_db()

    print(f"\n{'='*60}")
    print(f"Running {scraper.source_name} scraper...")
    print(f"{'='*60}")

    result = {
        'source': scraper.source_name,
        'saved': 0,
        'skipped': 0,
        'scraped': 0,
        'error': None
    }

    try:
        events = scraper.scrape()
        result['scraped'] = len(events)
        print(f"Scraped {len(events)} events from {scraper.source_name}")

        # Save events to database
        saved_count = 0
        skipped_count = 0

        for event in events:
            # Check if event already exists
            if event.url and event.event_date:
                if db.event_exists(event.url, event.event_date):
                    skipped_count += 1
                    continue

            # Insert event
            event_id = db.insert_event(event)
            if event_id:
                saved_count += 1
                print(f"✓ [{scraper.source_name}] Saved: {event.title}")
            else:
                print(f"✗ [{scraper.source_name}] Failed to save: {event.title}")

        result['saved'] = saved_count
        result['skipped'] = skipped_count
        print(f"\n[{scraper.source_name}] Summary: {saved_count} saved, {skipped_count} skipped (duplicates)")

    except Exception as e:
        result['error'] = str(e)
        print(f"✗ Error running {scraper.source_name} scraper: {e}")
        import traceback
        traceback.print_exc()

    return result


def main():
    """Main function to run all scrapers."""
    if '--no-logo-fetch' in sys.argv:
        os.environ['SCRAPER_DISABLE_LOGOS'] = 'true'

    print("\n" + "="*60)
    print("LA Events Aggregator - Scraper Runner")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Initialize database
    db = Database(config.DATABASE_PATH)
    print(f"\n✓ Database initialized: {config.DATABASE_PATH}")

    # Initialize all enabled scrapers from shared registry.
    scrapers = instantiate_enabled_scrapers()

    print(f"\n✓ Loaded {len(scrapers)} scrapers")

    # Run scrapers in parallel using ThreadPoolExecutor
    total_start = datetime.now()

    # Use a reasonable number of workers (max 5-10 concurrent scrapers)
    max_workers = min(10, len(scrapers))
    print(f"\n{'='*60}")
    print(f"Running {len(scrapers)} scrapers in parallel with {max_workers} workers")
    print(f"{'='*60}\n")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all scraper jobs
        future_to_scraper = {executor.submit(run_scraper, scraper): scraper for scraper in scrapers}

        # Process results as they complete
        for future in as_completed(future_to_scraper):
            scraper = future_to_scraper[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"✗ Exception in {scraper.source_name}: {e}")
                results.append({
                    'source': scraper.source_name,
                    'saved': 0,
                    'skipped': 0,
                    'scraped': 0,
                    'error': str(e)
                })

    total_time = (datetime.now() - total_start).total_seconds()

    # Final summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Print detailed results
    print("\nResults by Source:")
    print("-" * 60)
    total_scraped = 0
    total_saved = 0
    total_skipped = 0
    failed_sources = []

    for result in results:
        status = "✓" if result['error'] is None else "✗"
        print(f"{status} {result['source']}: {result['scraped']} scraped, {result['saved']} saved, {result['skipped']} skipped")
        total_scraped += result['scraped']
        total_saved += result['saved']
        total_skipped += result['skipped']
        if result['error']:
            failed_sources.append(result['source'])

    print("-" * 60)
    print(f"TOTALS: {total_scraped} scraped, {total_saved} saved, {total_skipped} skipped")

    if failed_sources:
        print(f"\nFailed sources ({len(failed_sources)}): {', '.join(failed_sources)}")

    # Count total events in database
    events = db.get_all_events(limit=10000)
    print(f"\nTotal events in database: {len(events)}")
    print("="*60 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
