"""
Unit tests for the Timeout LA scraper's HTML detail-page parsing.

Fully offline: fetch_page and the geocoder are replaced with fixtures that
mirror Timeout's markup (Address block, "Dates and times" occurrence rows).
Dates are relative to today so the tests do not rot.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.timeout import TimeoutScraper

HAMMER = (34.0592, -118.4435)      # Westwood: inside the coverage area
DOWNTOWN = (34.0505, -118.2440)    # Ahmanson Theatre: outside


class FakeGeocoder:
    def geocode_with_fallback(self, address, venue_name=None):
        return HAMMER if "10899 Wilshire" in (address or "") else DOWNTOWN


def _card(slug, title, until):
    return f"""
    <article class="tile">
      <a data-testid="tile-link_testID" href="/los-angeles/things-to-do/{slug}">
        <h3 data-testid="tile-title_testID">{title}</h3>
      </a>
      <time datetime="{until.strftime('%Y-%m-%dT23:59:59-08:00')}">Until {until:%b} {until.day}, {until.year}</time>
    </article>"""


def _row(when, name=None):
    name_html = f'<span class="_name_1uzv8_69">{name}</span>' if name else ""
    return f"""
    <div class="_articleRow_1uzv8_1"><article class="_article_1uzv8_1">
      <time datetime="{when.strftime('%Y-%m-%dT%H:%M:00-08:00')}"><span>x</span></time>
      <span class="_venueName_1uzv8_47">{name_html}<a href="/v">Venue</a></span>
    </article></div>"""


def _detail(venue, address_lines, rows, price="Price: $20 general admission"):
    dds = "".join(f"<dd>{line}</dd>" for line in address_lines)
    return f"""<html><head><meta property="og:image" content="https://img/x.jpg"></head><body>
    <div data-section="details"><dl><dt>Address</dt><dd><a href="/v">{venue}</a></dd>{dds}</dl></div>
    <div data-section="price"><dl><dt>Price:</dt><dd>{price.split(': ', 1)[1]}</dd></dl></div>
    <section data-section-name="occurrences">{''.join(rows)}</section>
    </body></html>"""


def _run(listing, details):
    s = TimeoutScraper()
    s.geocoding_service = FakeGeocoder()
    pages = {s.events_url: listing}
    pages.update({f"https://www.timeout.com/los-angeles/things-to-do/{k}": v for k, v in details.items()})
    s.prefetch_pages = lambda urls, **kw: None
    s.fetch_page = lambda url, retry=3: pages.get(url)
    return s.scrape()


def _today(days=0, hour=19, minute=30):
    d = datetime.now() + timedelta(days=days)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0)


@pytest.mark.unit
def test_named_occurrences_become_separate_dated_events():
    d1, d2 = _today(2), _today(9)
    past = _today(-5)
    listing = f"<html><body>{_card('series', 'MoMA Contenders', _today(30))}</body></html>"
    detail = _detail(
        "Hammer Museum",
        ["10899 Wilshire Blvd", "Los Angeles", "90024"],
        [_row(past, "Old Film"), _row(d1, "The Invite"), _row(d2, "La bola negra")],
    )

    events = _run(listing, {"series": detail})

    assert [e.title for e in events] == [
        "MoMA Contenders: The Invite",
        "MoMA Contenders: La bola negra",
    ]
    assert events[0].event_date == d1  # real screening time, not a run start
    assert events[0].end_date is None
    assert events[0].venue_name == "Hammer Museum"  # not "The InviteHammer Museum"
    assert events[0].address == "10899 Wilshire Blvd, Los Angeles, CA 90024"
    assert events[0].price == 20.0


@pytest.mark.unit
def test_unnamed_rows_stay_a_single_run_event():
    until = _today(60)
    listing = f"<html><body>{_card('run', 'Big Exhibition', until)}</body></html>"
    detail = _detail(
        "Hammer Museum",
        ["10899 Wilshire Blvd", "Los Angeles", "90024"],
        [_row(_today(1, 11, 0)), _row(_today(2, 11, 0))],
    )

    events = _run(listing, {"run": detail})

    assert len(events) == 1
    e = events[0]
    assert e.title == "Big Exhibition"
    assert e.event_date.date() == datetime.now().date()
    assert e.end_date.date() == until.date()


@pytest.mark.unit
def test_non_westside_venue_is_dropped():
    listing = f"<html><body>{_card('far', 'Downtown Play', _today(10))}</body></html>"
    detail = _detail(
        "Ahmanson Theatre",
        ["The Music Center", "135 N Grand Ave", "Los Angeles", "90012"],
        [_row(_today(1))],
    )

    assert _run(listing, {"far": detail}) == []


@pytest.mark.unit
def test_address_block_variants():
    s = TimeoutScraper()
    soup = s.parse_html(_detail("Venue X", ["The Music Center", "135 N Grand Ave", "Los Angeles", "90012"], []))
    assert s._venue_and_address(soup) == ("Venue X", "135 N Grand Ave, Los Angeles, CA 90012")

    soup = s.parse_html(_detail("Location T.B.A.", ["Los Angeles"], []))
    assert s._venue_and_address(soup) == ("Location T.B.A.", "Location T.B.A., Los Angeles, CA")
