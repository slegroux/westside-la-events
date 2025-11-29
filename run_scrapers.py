#!/usr/bin/env python3
"""
Optimized async script to run all event scrapers concurrently.

Key improvements over run_scrapers.py:
1. async/await pattern for I/O-bound web scraping (5-10x faster)
2. Single process - no SQLite locking issues
3. Concurrent HTTP requests with connection pooling
4. Configurable concurrency limits
5. Better error handling and progress tracking
6. Optional scraper selection via command line

Why async vs multiprocessing for scrapers:
- Web scraping is I/O-bound (waiting for HTTP responses)
- async can handle 100+ concurrent requests efficiently
- Single process = no database lock contention
- Lower memory overhead than multiprocessing
"""
import sys
import argparse
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import config
from src.data.database import Database
from src.data.models import Event

# Import all scrapers
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
from src.scrapers.getty_center import GettyCenterScraper
from src.scrapers.getty_villa import GettyVillaScraper
from src.scrapers.skirball import SkirballScraper
from src.scrapers.geffen_playhouse import GeffenPlayhouseScraper
from src.scrapers.broad_stage import BroadStageScraper
from src.scrapers.nuart_theatre import NuartTheatreScraper
from src.scrapers.mccabes import McCabesScraper
from src.scrapers.bergamot_station import BergamotStationScraper
from src.scrapers.fowler_museum import FowlerMuseumScraper
from src.scrapers.sm_farmers_market import SantaMonicaFarmersMarketScraper
from src.scrapers.william_turner import WilliamTurnerScraper
from src.scrapers.sounds_like_la import SoundsLikeLAScraper
from src.scrapers.brightside import BrightsideScraper
from src.scrapers.old_town_music_hall import OldTownMusicHallScraper
from src.scrapers.tripp import TrippScraper
from src.scrapers.la_puglia import LaPugliaScraper
from src.scrapers.recreation_cafe import RecreationCafeScraper
from src.scrapers.victorian import VictorianScraper
from src.scrapers.papille_gustative import PapilleGustativeScraper
from src.scrapers.jamesons_pub import JamesonsPubScraper


# Scraper class mapping
SCRAPER_MAP = {
    'santa_monica': SantaMonicaScraper,
    'timeout': TimeoutScraper,
    'kcrw': KCRWScraper,
    'laist': LAistScraper,
    'discover_la': DiscoverLAScraper,
    'eventbrite': EventbriteScraper,
    'ucla': UCLAScraper,
    'hammer': HammerScraper,
    'lacma': LACMAScraper,
    'venice_beach': VeniceBeachScraper,
    'weho': WestHollywoodScraper,
    'culver_city': CulverCityScraper,
    'meetup': MeetupScraper,
    'venice_west': VeniceWestScraper,
    'winston_house': WinstonHouseScraper,
    'westside_comedy': WestsideComedyScraper,
    'aviator_nation': AviatorNationScraper,
    'gnarwhal': GnarwhalScraper,
    'penmar': PenmarScraper,
    'itk_la': ITKLAScraper,
    'nerd_nite': NerdNiteScraper,
    'resident_advisor': ResidentAdvisorScraper,
    'iic_la': IICLAScraper,
    'afdela': AFdelaScraper,
    'raymond_kabbaz': RaymondKabbazScraper,
    'ucla_botanical': UCLABotanicalScraper,
    'parks_ca': ParksCaliforniaScraper,
    'kinn': KinnScraper,
    'casual_creative': CasualCreativeScraper,
    'latechevents': LATechEventsScraper,
    'beyond_baroque': BeyondBaroqueScraper,
    'apero_francophone': AperoFrancophoneScraper,
    'aero_theater': AeroTheaterScraper,
    'laemmle_monica': LaemmleMonicaScraper,
    'mudwtr': MudWtrScraper,
    'getty_center': GettyCenterScraper,
    'getty_villa': GettyVillaScraper,
    'skirball': SkirballScraper,
    'geffen_playhouse': GeffenPlayhouseScraper,
    'broad_stage': BroadStageScraper,
    'nuart_theatre': NuartTheatreScraper,
    'mccabes': McCabesScraper,
    'bergamot_station': BergamotStationScraper,
    'fowler_museum': FowlerMuseumScraper,
    'sm_farmers_market': SantaMonicaFarmersMarketScraper,
    'william_turner': WilliamTurnerScraper,
    'sounds_like_la': SoundsLikeLAScraper,
    'brightside': BrightsideScraper,
    'old_town_music_hall': OldTownMusicHallScraper,
    'tripp': TrippScraper,
    'la_puglia': LaPugliaScraper,
    'recreation_cafe': RecreationCafeScraper,
    'victorian': VictorianScraper,
    'papille_gustative': PapilleGustativeScraper,
    'jamesons_pub': JamesonsPubScraper,
}


class ScraperResult:
    """Container for scraper results"""
    def __init__(self, source: str):
        self.source = source
        self.events: List[Event] = []
        self.error: Optional[str] = None
        self.duration: float = 0.0

    @property
    def count(self) -> int:
        return len(self.events)

    @property
    def success(self) -> bool:
        return self.error is None


async def run_scraper_async(
    scraper_name: str,
    executor: ThreadPoolExecutor,
    semaphore: asyncio.Semaphore
) -> ScraperResult:
    """
    Run a single scraper asynchronously.

    Since our scrapers use synchronous requests library, we run them
    in a thread pool executor to avoid blocking the event loop.

    Args:
        scraper_name: Name of the scraper to run
        executor: ThreadPoolExecutor for running sync code
        semaphore: Semaphore to limit concurrent scrapers

    Returns:
        ScraperResult with events or error
    """
    result = ScraperResult(scraper_name)

    async with semaphore:  # Limit concurrent scrapers
        start_time = datetime.now()

        try:
            # Initialize scraper
            scraper_class = SCRAPER_MAP[scraper_name]
            scraper = scraper_class()

            print(f"[{scraper_name}] Starting...")

            # Run scraper in thread pool (since it's sync code)
            loop = asyncio.get_event_loop()
            events = await loop.run_in_executor(executor, scraper.scrape)

            result.events = events
            result.duration = (datetime.now() - start_time).total_seconds()

            print(f"✓ [{scraper_name}] Scraped {len(events)} events in {result.duration:.1f}s")

        except Exception as e:
            result.error = str(e)
            result.duration = (datetime.now() - start_time).total_seconds()
            print(f"✗ [{scraper_name}] Error: {e}")
            import traceback
            traceback.print_exc()

    return result


async def run_all_scrapers_async(
    scraper_names: List[str],
    max_concurrent: int = 10
) -> List[ScraperResult]:
    """
    Run all scrapers concurrently with a concurrency limit.

    Args:
        scraper_names: List of scraper names to run
        max_concurrent: Maximum number of concurrent scrapers

    Returns:
        List of ScraperResult objects
    """
    # Create thread pool for running sync scrapers
    # Use fewer threads than scrapers since they're mostly I/O bound
    max_workers = min(max_concurrent, len(scraper_names))
    executor = ThreadPoolExecutor(max_workers=max_workers)

    # Semaphore to limit concurrent scrapers
    semaphore = asyncio.Semaphore(max_concurrent)

    print(f"\n{'='*60}")
    print(f"Running {len(scraper_names)} scrapers concurrently")
    print(f"Max concurrent: {max_concurrent}")
    print(f"Thread pool workers: {max_workers}")
    print(f"{'='*60}\n")

    # Create tasks for all scrapers
    tasks = [
        run_scraper_async(name, executor, semaphore)
        for name in scraper_names
    ]

    # Run all tasks concurrently and gather results
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Cleanup executor
    executor.shutdown(wait=True)

    return results


def insert_events_to_db(db: Database, results: List[ScraperResult]) -> Dict[str, int]:
    """
    Insert all scraped events into database.

    Args:
        db: Database instance
        results: List of scraper results

    Returns:
        Dict with counts: saved, skipped, total
    """
    print(f"\n{'='*60}")
    print("Inserting events into database...")
    print(f"{'='*60}\n")

    total_saved = 0
    total_skipped = 0
    total_scraped = 0

    for result in results:
        if not result.success:
            continue

        saved = 0
        skipped = 0

        for event in result.events:
            # Check for duplicates
            if event.url and event.event_date:
                if db.event_exists(event.url, event.event_date):
                    skipped += 1
                    continue

            # Insert event
            event_id = db.insert_event(event)
            if event_id:
                saved += 1

        total_saved += saved
        total_skipped += skipped
        total_scraped += result.count

        if result.count > 0:
            print(f"✓ [{result.source}] {saved} saved, {skipped} skipped")

    return {
        'saved': total_saved,
        'skipped': total_skipped,
        'total': total_scraped
    }


async def main_async():
    """Main async function to run all scrapers."""
    parser = argparse.ArgumentParser(
        description='Run LA events scrapers with async optimization'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=10,
        help='Maximum concurrent scrapers (default: 10)'
    )
    parser.add_argument(
        '--scrapers',
        nargs='+',
        help='Specific scrapers to run (default: all enabled)'
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("LA Events Aggregator - Async Scraper Runner")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # Initialize database
    db = Database(config.DATABASE_PATH)
    print(f"\n✓ Database initialized: {config.DATABASE_PATH}")

    # Determine which scrapers to run
    if args.scrapers:
        # Validate scraper names
        invalid_scrapers = [s for s in args.scrapers if s not in SCRAPER_MAP]
        if invalid_scrapers:
            print(f"✗ Invalid scraper names: {', '.join(invalid_scrapers)}")
            print(f"Available scrapers: {', '.join(sorted(SCRAPER_MAP.keys()))}")
            sys.exit(1)
        scraper_names = args.scrapers
    else:
        # Use all enabled scrapers from config
        scraper_names = [
            name for name in SCRAPER_MAP.keys()
            if config.EVENT_SOURCES.get(name, {}).get('enabled', False)
        ]

    print(f"✓ Will run {len(scraper_names)} scrapers")

    # Run scrapers concurrently
    total_start = datetime.now()

    results = await run_all_scrapers_async(
        scraper_names,
        max_concurrent=args.max_concurrent
    )

    scrape_time = (datetime.now() - total_start).total_seconds()
    print(f"\n✓ Scraping completed in {scrape_time:.2f}s")

    # Insert events into database
    insert_start = datetime.now()
    counts = insert_events_to_db(db, results)
    insert_time = (datetime.now() - insert_start).total_seconds()

    total_time = scrape_time + insert_time

    # Calculate statistics
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    # Final summary
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print("="*60)
    print(f"Scraping time:   {scrape_time:.2f}s")
    print(f"DB insert time:  {insert_time:.2f}s")
    print(f"Total time:      {total_time:.2f}s")
    print(f"Finished at:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\nResults:")
    print("-" * 60)
    print(f"Successful:      {len(successful)}/{len(results)} scrapers")
    print(f"Failed:          {len(failed)}/{len(results)} scrapers")
    print(f"Total scraped:   {counts['total']} events")
    print(f"Saved:           {counts['saved']} events")
    print(f"Skipped:         {counts['skipped']} duplicates")

    if failed:
        print(f"\nFailed sources: {', '.join(r.source for r in failed)}")

    # Performance stats
    if counts['total'] > 0:
        print("\nPerformance:")
        print("-" * 60)
        avg_time = total_time / len(scraper_names)
        throughput = counts['total'] / total_time
        print(f"Avg time/scraper: {avg_time:.2f}s")
        print(f"Throughput:       {throughput:.1f} events/second")

        # Show fastest and slowest scrapers
        successful_sorted = sorted(successful, key=lambda r: r.duration)
        if successful_sorted:
            fastest = successful_sorted[0]
            slowest = successful_sorted[-1]
            print(f"Fastest:          {fastest.source} ({fastest.duration:.1f}s)")
            print(f"Slowest:          {slowest.source} ({slowest.duration:.1f}s)")

    # Database stats
    all_events = db.get_all_events(limit=10000)
    print(f"\nTotal events in database: {len(all_events)}")
    print("="*60 + "\n")

    # Upload to Cloud Storage if running in production
    import os
    if os.getenv('ENVIRONMENT') == 'production' and counts['saved'] > 0:
        print("\n" + "="*60)
        print("UPLOADING TO CLOUD STORAGE")
        print("="*60)

        import subprocess
        bucket = 'gs://westside-la-events-data'

        try:
            # Upload events database
            print("Uploading events.db...")
            subprocess.run(
                ['gsutil', 'cp', config.DATABASE_PATH, f'{bucket}/events.db'],
                check=True,
                timeout=60
            )
            print("✓ events.db uploaded")

            # Upload analytics database
            if os.path.exists('data/analytics.db'):
                print("Uploading analytics.db...")
                subprocess.run(
                    ['gsutil', 'cp', 'data/analytics.db', f'{bucket}/analytics.db'],
                    check=True,
                    timeout=60
                )
                print("✓ analytics.db uploaded")

            # Upload geocode cache
            if os.path.exists('data/geocode_cache.json'):
                print("Uploading geocode_cache.json...")
                subprocess.run(
                    ['gsutil', 'cp', 'data/geocode_cache.json', f'{bucket}/geocode_cache.json'],
                    check=True,
                    timeout=60
                )
                print("✓ geocode_cache.json uploaded")

            print("\n✓ All files uploaded to Cloud Storage")
            print("="*60 + "\n")

        except subprocess.TimeoutExpired:
            print("✗ Upload timed out")
        except subprocess.CalledProcessError as e:
            print(f"✗ Upload failed: {e}")
        except Exception as e:
            print(f"✗ Upload error: {e}")
    elif os.getenv('ENVIRONMENT') == 'production':
        print("\n⊘ No new events saved, skipping Cloud Storage upload\n")


def main():
    """Entry point that runs the async main function."""
    try:
        # Run async main
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
