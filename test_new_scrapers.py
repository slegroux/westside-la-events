#!/usr/bin/env python3
"""Test all new scrapers in parallel."""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Import all new scrapers
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

def run_scraper(scraper):
    try:
        print(f'Starting {scraper.source_name}...')
        events = scraper.scrape()
        return {'source': scraper.source_name, 'count': len(events), 'error': None}
    except Exception as e:
        return {'source': scraper.source_name, 'count': 0, 'error': str(e)}

scrapers = [
    GettyCenterScraper(),
    GettyVillaScraper(),
    SkirballScraper(),
    GeffenPlayhouseScraper(),
    BroadStageScraper(),
    NuartTheatreScraper(),
    McCabesScraper(),
    BergamotStationScraper(),
    FowlerMuseumScraper(),
    SantaMonicaFarmersMarketScraper()
]

print('\n' + '='*60)
print(f'Testing {len(scrapers)} new scrapers in parallel')
print('='*60 + '\n')

start = datetime.now()
results = []

with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_scraper = {executor.submit(run_scraper, s): s for s in scrapers}
    for future in as_completed(future_to_scraper):
        result = future.result()
        results.append(result)
        status = '✓' if result['error'] is None else '✗'
        print(f"{status} {result['source']}: {result['count']} events")

elapsed = (datetime.now() - start).total_seconds()

print('\n' + '='*60)
print(f'Completed in {elapsed:.2f} seconds')
total = sum(r['count'] for r in results)
failed = [r['source'] for r in results if r['error']]
print(f'Total events: {total}')
if failed:
    print(f"Failed scrapers: {', '.join(failed)}")
print('='*60)
