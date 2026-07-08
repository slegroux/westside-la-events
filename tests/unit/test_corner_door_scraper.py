"""
Unit tests for The Corner Door scraper.

Fully offline: fetch_page is monkeypatched to return hand-authored Squarespace
markup, so no network or browser is launched. Dates are generated relative to
today so weekday-anchored year resolution is exercised deterministically.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.corner_door import CornerDoorScraper


def _md(dt):
    """Format a date the way the venue writes it: 'Weekday month.day'."""
    return f"{dt.strftime('%A')} {dt.month}.{dt.day}"


def _page(*blocks):
    body = "\n".join(blocks)
    return f'<html><body><article class="sections">{body}</article></body></html>'


def _run(scraper, html):
    scraper.fetch_page = lambda url, retry=3: html
    return scraper.scrape()


@pytest.mark.unit
def test_parses_upcoming_event_with_inferred_year(mock_geocoding_service):
    """A dateless (year-omitted) upcoming event resolves via its weekday."""
    when = (datetime.now() + timedelta(days=10)).replace(microsecond=0)
    html = _page(
        "<h3>MONTH</h3>",
        "<h4>MungoSound</h4>",
        f"<p><strong>{_md(when)}</strong> 9pm - Close</p>",
        "<p>Special Guest DJ: Cruel Mistress</p>",
    )

    events = _run(CornerDoorScraper(), html)

    assert len(events) == 1
    e = events[0]
    assert e.title == "MungoSound"
    assert e.event_date.date() == when.date()
    assert e.event_date.hour == 21  # 9pm
    assert e.category == "Nightlife"
    assert e.venue_name == "The Corner Door"
    assert abs(e.latitude - 33.9969765) < 1e-6
    assert "Cruel Mistress" in e.description
    # No ticket link on this block -> falls back to the listing page.
    assert e.url == CornerDoorScraper.LISTING_URL


@pytest.mark.unit
def test_explicit_year_and_ticket_link_and_category(mock_geocoding_service):
    """Explicit 2-digit year is honored; ticket link and comedy category map."""
    future = datetime.now() + timedelta(days=400)  # comfortably next year
    yy = future.strftime("%y")
    html = _page(
        "<h4>The Super Dope Comedy Show</h4>",
        f"<p>{future.strftime('%A')} {future.month}.{future.day}.{yy} 8pm</p>",
        "<p>Hosted by Max Kestenbaum</p>",
        "<p>Tickets:</p>",
        '<p><a href="https://www.eventbrite.com/e/super-dope-123">link</a></p>',
    )

    events = _run(CornerDoorScraper(), html)

    assert len(events) == 1
    e = events[0]
    assert e.event_date.year == future.year
    assert e.category == "Comedy"
    assert e.url == "https://www.eventbrite.com/e/super-dope-123"
    # Bare "Tickets:" label and the raw URL are kept out of the description.
    assert "Tickets" not in e.description
    assert "http" not in e.description


@pytest.mark.unit
def test_skips_past_events(mock_geocoding_service):
    """A past-dated block (e.g. a stale page) is dropped."""
    past = datetime.now() - timedelta(days=20)
    html = _page(
        "<h4>Old Vinyl Night</h4>",
        f"<p>{_md(past)} 8pm - Close</p>",
        "<p>DJs: Someone</p>",
    )

    assert _run(CornerDoorScraper(), html) == []


@pytest.mark.unit
def test_dedupes_repeated_block(mock_geocoding_service):
    """The same title on the same date is emitted only once."""
    when = datetime.now() + timedelta(days=7)
    block = (
        "<h4>Trivia Night!</h4>"
        f"<p>{_md(when)} 7pm - 9pm</p>"
        "<p>Hosted by Kevan &amp; Matt</p>"
    )
    events = _run(CornerDoorScraper(), _page(block, block))

    assert len(events) == 1
    assert events[0].category == "Community"
