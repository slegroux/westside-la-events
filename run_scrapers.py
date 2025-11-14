#!/usr/bin/env python3
"""
Script to run all event scrapers and populate the database.
"""
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import config
from src.data.database import Database
from src.scrapers.santa_monica import SantaMonicaScraper
from src.scrapers.timeout import TimeoutScraper
from src.scrapers.kcrw import KCRWScraper
from src.scrapers.laist import LAistScraper
from src.scrapers.discover_la import DiscoverLAScraper
from src.scrapers.eventbrite import EventbriteScraper
from src.scrapers.ucla import UCLAScraper
from src.scrapers.hammer import HammerScraper
from src.scrapers.lacma import LACMAScraper
from src.scrapers.venice_beach import VeniceBeachScraper
from src.scrapers.west_hollywood import WestHollywoodScraper
from src.scrapers.culver_city import CulverCityScraper

# Other optional scrapers:
from src.scrapers.meetup import MeetupScraper
from src.scrapers.venice_west import VeniceWestScraper
from src.scrapers.winston_house import WinstonHouseScraper
from src.scrapers.westside_comedy import WestsideComedyScraper
from src.scrapers.aviator_nation import AviatorNationScraper
from src.scrapers.gnarwhal import GnarwhalScraper
from src.scrapers.penmar import PenmarScraper
from src.scrapers.itk_la import ITKLAScraper
from src.scrapers.nerd_nite import NerdNiteScraper
from src.scrapers.resident_advisor import ResidentAdvisorScraper
from src.scrapers.iic_la import IICLAScraper
from src.scrapers.afdela import AFdelaScraper
from src.scrapers.raymond_kabbaz import RaymondKabbazScraper
from src.scrapers.ucla_botanical import UCLABotanicalScraper
from src.scrapers.parks_ca import ParksCaliforniaScraper
from src.scrapers.kinn import KinnScraper
from src.scrapers.casual_creative import CasualCreativeScraper
from src.scrapers.latechevents import LATechEventsScraper
from src.scrapers.beyond_baroque import BeyondBaroqueScraper
from src.scrapers.apero_francophone import AperoFrancophoneScraper
from src.scrapers.aero_theater import AeroTheaterScraper
from src.scrapers.laemmle_monica import LaemmleMonicaScraper
from src.scrapers.mudwtr import MudWtrScraper

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

    if config.EVENT_SOURCES.get('laist', {}).get('enabled'):
        scrapers.append(LAistScraper())

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

    if config.EVENT_SOURCES.get('penmar', {}).get('enabled'):
        scrapers.append(PenmarScraper())

    if config.EVENT_SOURCES.get('itk_la', {}).get('enabled'):
        scrapers.append(ITKLAScraper())

    if config.EVENT_SOURCES.get('nerd_nite', {}).get('enabled'):
        scrapers.append(NerdNiteScraper())

    if config.EVENT_SOURCES.get('resident_advisor', {}).get('enabled'):
        scrapers.append(ResidentAdvisorScraper())

    if config.EVENT_SOURCES.get('iic_la', {}).get('enabled'):
        scrapers.append(IICLAScraper())

    if config.EVENT_SOURCES.get('afdela', {}).get('enabled'):
        scrapers.append(AFdelaScraper())

    if config.EVENT_SOURCES.get('raymond_kabbaz', {}).get('enabled'):
        scrapers.append(RaymondKabbazScraper())

    if config.EVENT_SOURCES.get('ucla_botanical', {}).get('enabled'):
        scrapers.append(UCLABotanicalScraper())

    if config.EVENT_SOURCES.get('parks_ca', {}).get('enabled'):
        scrapers.append(ParksCaliforniaScraper())

    if config.EVENT_SOURCES.get('kinn', {}).get('enabled'):
        scrapers.append(KinnScraper())

    if config.EVENT_SOURCES.get('casual_creative', {}).get('enabled'):
        scrapers.append(CasualCreativeScraper())

    if config.EVENT_SOURCES.get('latechevents', {}).get('enabled'):
        scrapers.append(LATechEventsScraper())

    if config.EVENT_SOURCES.get('beyond_baroque', {}).get('enabled'):
        scrapers.append(BeyondBaroqueScraper())

    if config.EVENT_SOURCES.get('apero_francophone', {}).get('enabled'):
        scrapers.append(AperoFrancophoneScraper())

    if config.EVENT_SOURCES.get('ucla', {}).get('enabled'):
        scrapers.append(UCLAScraper())

    if config.EVENT_SOURCES.get('hammer', {}).get('enabled'):
        scrapers.append(HammerScraper())

    if config.EVENT_SOURCES.get('lacma', {}).get('enabled'):
        scrapers.append(LACMAScraper())

    if config.EVENT_SOURCES.get('venice_beach', {}).get('enabled'):
        scrapers.append(VeniceBeachScraper())

    if config.EVENT_SOURCES.get('weho', {}).get('enabled'):
        scrapers.append(WestHollywoodScraper())

    if config.EVENT_SOURCES.get('culver_city', {}).get('enabled'):
        scrapers.append(CulverCityScraper())

    if config.EVENT_SOURCES.get('aero_theater', {}).get('enabled'):
        scrapers.append(AeroTheaterScraper())

    if config.EVENT_SOURCES.get('laemmle_monica', {}).get('enabled'):
        scrapers.append(LaemmleMonicaScraper())

    if config.EVENT_SOURCES.get('mudwtr', {}).get('enabled'):
        scrapers.append(MudWtrScraper())

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
