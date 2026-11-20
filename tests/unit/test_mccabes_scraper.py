"""
Unit tests for the McCabe's Guitar Shop scraper.

Fully offline: fetch_page (landing page) and fetch_json (WooCommerce Store API)
are monkeypatched with small hand-authored fixtures. Dates are relative to
today so the tests do not rot.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.mccabes import McCabesScraper

BASE = "https://www.mccabes.com/product"


def _card(slug, title, when, sold_out_text=""):
    date = f"{when.strftime('%a %b')} {when.day} {when.year} | 8pm"
    url = f"{BASE}/{slug}/"
    return f"""
    <div class="fooevents-calendar-list-item col-md-4"><div class="event_content">
      <a href="{url}"><div class="event-card">
        <div class="main-img" style="background-image: url(https://www.mccabes.com/img/{slug}.jpg);"></div>
      </div></a>
      <div class="event_copy">
        <p class="fooevents-shortcode-date"><i class="far"></i>{date}</p>
        <h3 class="fooevents-shortcode-title"><a href="{url}">{title}</a></h3>
        {sold_out_text}
      </div></div></div>"""


def _page(*cards):
    return f'<html><body><div class="fooevents-calendar-list row">{"".join(cards)}</div></body></html>'


def _product(slug, cents, in_stock=True, blurb="A great songwriter."):
    return {
        "permalink": f"{BASE}/{slug}/",
        "is_in_stock": in_stock,
        "short_description": f"<h3>Fri, Jan 8th, 8:00 pm</h3><div><p>{blurb}</p></div>",
        "prices": {"price": str(cents), "currency_minor_unit": 2},
    }


def _run(html, products):
    s = McCabesScraper()
    fetched = []
    s.fetch_page = lambda url, retry=3: fetched.append(url) or html
    s.fetch_json = lambda url, **kw: products
    return s.scrape(), fetched


@pytest.mark.unit
def test_parses_event_with_price_and_description(mock_geocoding_service):
    when = datetime.now() + timedelta(days=12)
    html = _page(_card("joy-clark", "Joy Clark / opener Stella Prince", when))

    events, fetched = _run(html, [_product("joy-clark", 3200, blurb="Bluesy and bright.")])

    assert len(events) == 1
    e = events[0]
    assert e.title == "Joy Clark / opener Stella Prince"
    assert e.event_date.date() == when.date()
    assert e.event_date.hour == 20
    assert e.price == 32.0
    assert e.price_note == "$32.00"
    assert e.category == "Music"
    assert e.venue_name == "McCabe's Guitar Shop"
    assert e.url == f"{BASE}/joy-clark/"
    assert e.image_url.endswith("/joy-clark.jpg")
    assert e.description == "Bluesy and bright."
    # Only the landing page is fetched as HTML: no per-event detail requests.
    assert len(fetched) == 1


@pytest.mark.unit
def test_all_cards_kept_beyond_old_detail_cap(mock_geocoding_service):
    """No cap on events: 40 cards -> 40 events, from one page + one API call."""
    base = datetime.now() + timedelta(days=3)
    cards = [_card(f"show-{i}", f"Show {i}", base + timedelta(days=i)) for i in range(40)]

    events, fetched = _run(_page(*cards), [_product(f"show-{i}", 2500) for i in range(40)])

    assert len(events) == 40
    assert len(fetched) == 1


@pytest.mark.unit
def test_events_survive_when_store_api_fails(mock_geocoding_service):
    """Listing data alone is enough: events kept, price left empty."""
    when = datetime.now() + timedelta(days=5)
    html = _page(_card("sam-baker", "Sam Baker", when))

    events, _ = _run(html, None)

    assert len(events) == 1
    assert events[0].price is None
    assert events[0].price_note == ""


@pytest.mark.unit
def test_sold_out_from_stock_flag_or_listing_text(mock_geocoding_service):
    when = datetime.now() + timedelta(days=8)
    html = _page(
        _card("a", "Out By Stock", when),
        _card("b", "Out By Text", when + timedelta(days=1), "<span>SOLD OUT</span>"),
    )

    events, _ = _run(html, [_product("a", 3000, in_stock=False)])

    notes = {e.title: e.price_note for e in events}
    assert notes == {"Out By Stock": "Sold out", "Out By Text": "Sold out"}


@pytest.mark.unit
def test_card_without_parseable_date_is_skipped(mock_geocoding_service):
    when = datetime.now() + timedelta(days=4)
    bad = _card("bad", "No Date Show", when).replace(
        f"{when.strftime('%a %b')} {when.day} {when.year} | 8pm", "Date TBA"
    )
    html = _page(bad, _card("ok", "Dated Show", when))

    events, _ = _run(html, [])

    assert [e.title for e in events] == ["Dated Show"]
