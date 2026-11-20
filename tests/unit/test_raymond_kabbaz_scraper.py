"""
Unit tests for the Théâtre Raymond Kabbaz scraper.

Fully offline: fetch_page/prefetch_pages are monkeypatched with small
Squarespace-shaped fixtures (a season page of image links plus show pages whose
second <h1> is a year-less "mon day - time" line). Dates are relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.raymond_kabbaz import RaymondKabbazScraper

BASE = 'https://www.theatreraymondkabbaz.com'


def _season_label(now):
    start = now.year if now.month >= 8 else now.year - 1
    return f'Season {start}-{start + 1}'


def _listing(now, *slugs):
    links = ''.join(f'<a href="/{s}"><img src="x.jpg"></a>' for s in slugs)
    nav = '<a href="/about-1">About</a>'
    return (
        f'<html><head><title>{_season_label(now)} &mdash; Théâtre Raymond Kabbaz</title></head>'
        f'<body><header>{nav}</header><main><h1>UPCOMING EVENTS</h1>{links}</main></body></html>'
    )


def _show(title, date_line, genre='Jazz Music'):
    return (
        '<html><body><main>'
        f'<h1>{title}</h1><h1>{date_line}</h1><h1>25% OFF</h1>'
        '<img src="https://images.squarespace-cdn.com/a.jpg?format=500w">'
        f'<p>Genre: {genre}</p><p>Duration: 75 minutes</p>'
        '<p>\U0001F1FA\U0001F1F8 English description here.</p>'
        '<p>\U0001F1EB\U0001F1F7 Description en francais.</p>'
        '</main></body></html>'
    )


def _fmt(dt, time=None):
    s = f"{dt.strftime('%b')} {dt.day}"
    return f'{s} - {time}' if time else s


def _run(pages):
    scraper = RaymondKabbazScraper()
    scraper.fetch_page = lambda url, retry=3: pages.get(url)
    scraper.prefetch_pages = lambda urls: None
    return scraper.scrape()


@pytest.mark.unit
def test_parses_show_pages_from_season_listing(mock_geocoding_service):
    now = datetime.now()
    soon = now + timedelta(days=10)
    pages = {
        f'{BASE}/upcoming-events': _listing(soon, 'jazz-night'),
        f'{BASE}/jazz-night': _show('Jazz Night', _fmt(soon, '8:00 PM')),
    }

    events = _run(pages)

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Jazz Night'
    assert e.event_date.date() == soon.date()
    assert (e.event_date.hour, e.event_date.minute) == (20, 0)
    assert e.url == f'{BASE}/jazz-night'
    assert e.category == 'Music'
    assert e.image_url == 'https://images.squarespace-cdn.com/a.jpg'
    assert 'English description' in e.description
    assert 'francais' not in e.description
    assert not e.price_note  # price unknown stays empty


@pytest.mark.unit
def test_nav_links_ignored_and_past_shows_dropped(mock_geocoding_service):
    now = datetime.now()
    past = now - timedelta(days=20)
    pages = {
        f'{BASE}/upcoming-events': _listing(past, 'old-show'),
        f'{BASE}/old-show': _show('Old Show', _fmt(past, '8:00 PM')),
        f'{BASE}/about-1': _show('About', _fmt(now + timedelta(days=5), '8:00 PM')),
    }

    assert _run(pages) == []


@pytest.mark.unit
def test_date_range_and_missing_date(mock_geocoding_service):
    now = datetime.now()
    # Next month, days 5-8: ranges never straddle a month boundary.
    start = (now.replace(day=1) + timedelta(days=32)).replace(day=5)
    end = start + timedelta(days=3)
    pages = {
        f'{BASE}/upcoming-events': _listing(start, 'festival', 'tbd'),
        f'{BASE}/festival': _show('Film Week', f'{start.strftime("%b")} {start.day}-{end.day}', genre='Feature Films'),
        f'{BASE}/tbd': _show('Mystery Show', 'coming soon'),
    }

    events = _run(pages)

    assert [e.title for e in events] == ['Film Week']
    e = events[0]
    assert e.event_date.date() == start.date()
    assert e.end_date.date() == end.date()
    assert e.category == 'Film'


@pytest.mark.unit
def test_empty_listing_returns_nothing(mock_geocoding_service):
    now = datetime.now()
    assert _run({f'{BASE}/upcoming-events': _listing(now)}) == []
    assert _run({}) == []
