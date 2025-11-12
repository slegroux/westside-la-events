#!/usr/bin/env python3
"""
Script to run all event scrapers and populate the database.
"""
import sys
from datetime import datetime

import config
from src.data.database import Database
from src.scrapers.santa_monica import SantaMonicaScraper
from src.scrapers.timeout import TimeoutScraper
from src.scrapers.kcrw import KCRWScraper
from src.scrapers.discover_la import DiscoverLAScraper
from src.scrapers.eventbrite import EventbriteScraper

# Other optional scrapers:
from src.scrapers.meetup import MeetupScraper
from src.scrapers.venice_west import VeniceWestScraper
from src.scrapers.winston_house import WinstonHouseScraper
from src.scrapers.westside_comedy import WestsideComedyScraper
from src.scrapers.aviator_nation import AviatorNationScraper
from src.scrapers.gnarwhal import GnarwhalScraper


def run_scraper(scraper, db):
    """
    Run a scraper and save events to database.

    Args:
        scraper: Scraper instance
        db: Database instance
    """
    print(f"\n{'='*60}")
    print(f"Running {scraper.source_name} scraper...")
    print(f"{'='*60}")

    try:
        events = scraper.scrape()
        print(f"Scraped {len(events)} events")

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
                print(f"✓ Saved: {event.title}")
            else:
                print(f"✗ Failed to save: {event.title}")

        print(f"\nSummary: {saved_count} saved, {skipped_count} skipped (duplicates)")

    except Exception as e:
        print(f"✗ Error running {scraper.source_name} scraper: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function to run all scrapers."""
    print("\n" + "="*60)
    print("LA Events Aggregator - Scraper Runner")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Initialize database
    db = Database(config.DATABASE_PATH)
    print(f"\n✓ Database initialized: {config.DATABASE_PATH}")

    # Initialize scrapers
    scrapers = []

    # Only add enabled scrapers
    if config.EVENT_SOURCES['santa_monica']['enabled']:
        scrapers.append(SantaMonicaScraper())

    if config.EVENT_SOURCES['timeout']['enabled']:
        scrapers.append(TimeoutScraper())

    if config.EVENT_SOURCES['kcrw']['enabled']:
        scrapers.append(KCRWScraper())

    if config.EVENT_SOURCES.get('discover_la', {}).get('enabled'):
        scrapers.append(DiscoverLAScraper())

    if config.EVENT_SOURCES.get('eventbrite', {}).get('enabled'):
        scrapers.append(EventbriteScraper())

    # Other optional scrapers:
    if config.EVENT_SOURCES.get('meetup', {}).get('enabled'):
        scrapers.append(MeetupScraper())

    if config.EVENT_SOURCES.get('venice_west', {}).get('enabled'):
        scrapers.append(VeniceWestScraper())

    if config.EVENT_SOURCES.get('winston_house', {}).get('enabled'):
        scrapers.append(WinstonHouseScraper())

    if config.EVENT_SOURCES.get('westside_comedy', {}).get('enabled'):
        scrapers.append(WestsideComedyScraper())

    if config.EVENT_SOURCES.get('aviator_nation', {}).get('enabled'):
        scrapers.append(AviatorNationScraper())

    if config.EVENT_SOURCES.get('gnarwhal', {}).get('enabled'):
        scrapers.append(GnarwhalScraper())

    # Add more web scrapers here as they are implemented
    # if config.EVENT_SOURCES['dola']['enabled']:
    #     scrapers.append(DoLAScraper())
    # if config.EVENT_SOURCES['ucla']['enabled']:
    #     scrapers.append(UCLAScraper())
    # etc.

    print(f"\n✓ Loaded {len(scrapers)} scrapers")

    # Run each scraper
    total_start = datetime.now()

    for scraper in scrapers:
        run_scraper(scraper, db)

    total_time = (datetime.now() - total_start).total_seconds()

    # Final summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Count total events in database
    events = db.get_all_events(limit=10000)
    print(f"Total events in database: {len(events)}")
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
