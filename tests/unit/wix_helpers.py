"""
Shared builders for the Wix Events scraper tests (Sam First, Highways).

They produce the home-page markup Wix server-renders (a JSON blob under
``"events":{"events":[...]}``), the event sitemap, and an event page's JSON-LD,
with every date generated relative to today in LA-local time.
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LA = ZoneInfo('America/Los_Angeles')


def future(days=10, hour=19, minute=30):
    """A naive LA-local datetime `days` from now."""
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def utc_iso(local):
    """Wix stores instants in UTC with a ``Z`` suffix."""
    return local.replace(tzinfo=LA).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def raw_event(slug, title, start, *, hours=3, status=0, price='16.80', sold_out=False,
              tbd=False, description='A night of music.', lat=33.9458, lng=-118.3934,
              venue='Sam First', address='6171 W Century Blvd #180, Los Angeles, CA 90045, USA'):
    ticketing = {'soldOut': sold_out}
    if price is not None:
        ticketing['lowestTicketPrice'] = {'amount': price, 'currency': 'USD'}
    return {
        'id': f'id-{slug}',
        'slug': slug,
        'title': title,
        'description': description,
        'about': '',
        'status': status,
        'mainImage': {'url': f'https://img.example/{slug}.jpg'},
        'location': {
            'name': venue,
            'address': address,
            'coordinates': {'lat': lat, 'lng': lng},
        },
        'scheduling': {'config': {
            'scheduleTbd': tbd,
            'startDate': utc_iso(start),
            'endDate': utc_iso(start + timedelta(hours=hours)),
            'timeZoneId': 'America/Los_Angeles',
        }},
        'registration': {'type': 2, 'ticketing': ticketing},
    }


def home_page(raw_events, has_more=False):
    """The Wix home page with the embedded events blob."""
    blob = json.dumps({'events': {'events': raw_events, 'hasMore': has_more, 'moreLoading': False}})
    return f'<html><body><script id="wix-warmup-data" type="application/json">{blob}</script></body></html>'


def sitemap(entries):
    """entries: [(slug, 'YYYY-MM-DD' lastmod)]."""
    urls = ''.join(
        f'<url><loc>https://www.samfirstbar.com/events/{slug}</loc><lastmod>{mod}</lastmod></url>'
        for slug, mod in entries
    )
    return f'<?xml version="1.0"?><urlset>{urls}</urlset>'


def event_page(title, start, *, low='28', sold_out=False, cancelled=False):
    """An event page whose only structured data is a schema.org Event."""
    ld = {
        '@type': 'Event',
        'name': title,
        'description': 'From the event page.',
        'startDate': start.replace(tzinfo=LA).isoformat(),
        'endDate': (start + timedelta(hours=3)).replace(tzinfo=LA).isoformat(),
        'eventStatus': 'https://schema.org/EventCancelled' if cancelled else 'https://schema.org/EventScheduled',
        'image': {'@type': 'ImageObject', 'url': 'https://img.example/page.jpg'},
        'offers': {
            '@type': 'AggregateOffer',
            'lowPrice': low,
            'availability': 'https://schema.org/SoldOut' if sold_out else 'https://schema.org/InStock',
        },
    }
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head></html>'


def run(scraper, pages):
    """Serve `pages` {url: html}; anything else fails to fetch."""
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    return scraper.scrape()
