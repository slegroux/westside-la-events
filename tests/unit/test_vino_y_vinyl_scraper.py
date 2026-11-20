"""
Unit tests for the Vino Y Vinyl (Universe host page) scraper.

Fully offline: fetch_page_js is monkeypatched. Dates are relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.vino_y_vinyl import VinoYVinylScraper

EMPTY_HOST = (
    "<html><body><h1>Vino y vinyl</h1><h2>Upcoming events</h2>"
    "<p>Vino y vinyl doesn't have any upcoming events.</p></body></html>"
)

HOST_PATH = "/events/vino-y-vinyl-night-tickets-AbC123"


def _event_page(title, when, address="222 Main St, Venice, CA 90291"):
    date_line = f"{when.strftime('%a')}, {when.strftime('%b')} {when.day}, {when.year} at 6-11:30 PM"
    return (
        f"<html><body><h1>{title}</h1><p>{title}</p><p>{date_line}</p>"
        f"<p>{address}</p><p>Tickets from $25</p></body></html>"
    )


def _run(pages):
    scraper = VinoYVinylScraper()
    scraper.fetch_page_js = lambda url, **kw: pages.get(url)
    return scraper, scraper.scrape()


@pytest.mark.unit
def test_empty_host_page_returns_no_events(mock_geocoding_service):
    scraper = VinoYVinylScraper()
    pages = {scraper.events_url: EMPTY_HOST}
    _, events = _run(pages)
    assert events == []


@pytest.mark.unit
def test_upcoming_event_is_parsed(mock_geocoding_service):
    when = (datetime.now() + timedelta(days=14)).replace(hour=18, minute=0)
    scraper = VinoYVinylScraper()
    event_url = f"{scraper.base_url}{HOST_PATH}"
    pages = {
        scraper.events_url: f'<html><a href="{HOST_PATH}">x</a></html>',
        event_url: _event_page("Vino Y Vinyl Night", when),
    }

    _, events = _run(pages)

    assert len(events) == 1
    e = events[0]
    assert e.title == "Vino Y Vinyl Night"
    assert e.event_date.date() == when.date()
    assert e.event_date.hour == 18
    assert e.price == 25.0
    assert e.price_note == ""
    assert e.url == event_url
