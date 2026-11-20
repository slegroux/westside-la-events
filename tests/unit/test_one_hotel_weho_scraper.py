"""
Unit tests for the 1 Hotel West Hollywood scraper.

Fully offline: fetch_page is monkeypatched to return hand-authored cards
shaped like the live Drupal view (title in an h2, "Thu | 19 | Nov" badge).
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.one_hotel_weho import OneHotelWeHoScraper


def _card(title, when, label="West Hollywood", space="Juniper Lounge",
          tag="h2", href="https://www.1hotels.com/west-hollywood/do/events/x"):
    return f"""
    <article class="event card"><div class="wrapper"><div class="media">
      <a href="{href}"><figure><img src="/img/a.jpg"/></figure>
        <div class="date"><span>{when.strftime('%a')}</span>
          <span><strong>{when.day}</strong></span><span>{when.strftime('%b')}</span></div>
        <div class="title">
          <div class="property"><span class="property-label">{label}</span>
            <span class="property-location">{space}</span></div>
          <{tag}>{title}</{tag}>
          <div class="location">Mondays</div>
        </div></a></div></div></article>"""


def _run(*cards):
    scraper = OneHotelWeHoScraper()
    html = "<html><body>" + "".join(cards) + "</body></html>"
    scraper.fetch_page = lambda url, retry=3: html
    scraper.fetch_page_js = lambda *a, **k: None
    return scraper.scrape()


@pytest.mark.unit
def test_card_with_h2_title_is_parsed(mock_geocoding_service):
    when = datetime.now() + timedelta(days=3)

    events = _run(_card("Martini Mondays", when))

    assert len(events) == 1
    e = events[0]
    assert e.title == "Martini Mondays"
    assert e.event_date.date() == when.date()
    assert e.venue_name == "1 Hotel West Hollywood — Juniper Lounge"
    assert e.image_url == "https://www.1hotels.com/img/a.jpg"
    assert e.price_note == ""


@pytest.mark.unit
def test_legacy_h3_title_still_parsed(mock_geocoding_service):
    when = datetime.now() + timedelta(days=3)
    events = _run(_card("Old Markup", when, tag="h3"))
    assert [e.title for e in events] == ["Old Markup"]


@pytest.mark.unit
def test_other_property_card_is_skipped(mock_geocoding_service):
    when = datetime.now() + timedelta(days=3)
    assert _run(_card("Elsewhere", when, label="Brooklyn Bridge")) == []
