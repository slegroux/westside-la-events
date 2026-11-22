"""
Unit tests for the UCLA Film & Television Archive scraper.

Fully offline: fetch_page_js serves hand-built rendered listing pages (the
Nuxt card markup) and fetch_page serves event pages. Dates are generated
relative to today.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.ucla_film_archive import UCLAFilmArchiveScraper


def _card(slug, title, when, series='Dorothy Dandridge', date_text=None):
    date_text = date_text or f"{when.strftime('%b')} {when.day}, {when.year}"
    return f'''
    <li class="block-card-three-column ftva list-item block" section-handle="ftvaEvent">
      <div class="image-block"><figure><img src="https://img.example/{slug}.jpg" alt=""></figure></div>
      <div class="meta"><div class="card-meta">
        <div class="category">{series}</div>
        <a href="/events/{slug}/" class="smart-link title">{title} <!----></a>
        <div class="date-time">
          <time class="schedule-item start-date">{date_text}</time>
          <time class="schedule-item parsed-time">{when.strftime('%I:%M %p').lstrip('0').lower()}</time>
        </div>
      </div></div>
    </li>'''


def _listing(cards, pages=1):
    nav = ''.join(f'<a href="/events/?page={n}/">{n}</a>' for n in range(1, pages + 1))
    return (
        '<html><body><ul class="list">' + ''.join(cards) + '</ul>'
        f'<div class="pagination-numbers">{nav}</div></body></html>'
    )


def _detail(venue='Billy Wilder Theater', tickets=('Free admission', 'No advance reservations'),
            description='A fine film.'):
    lis = ''.join(f'<li>{t}</li>' for t in tickets)
    return (
        '<html><body>'
        f'<div class="event-list location"><span><a href="#">{venue}</a></span></div>'
        f'<div class="rich-text event-description"><p>{description}</p></div>'
        f'<div class="ticket-info"><ul class="block-info-list">{lis}</ul></div>'
        '</body></html>'
    )


def _when(days, hour=19, minute=30):
    return (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)


def _run(pages, details=None):
    """pages: {page number: html}; details: {slug: html}."""
    scraper = UCLAFilmArchiveScraper()
    requested = []

    def fetch_page_js(url, wait_selector=None, timeout=30000):
        requested.append(url)
        number = int(url.split('page=')[1].rstrip('/')) if 'page=' in url else 1
        return pages.get(number)

    def fetch_page(url, retry=3):
        slug = url.rstrip('/').rsplit('/', 1)[-1]
        return (details or {}).get(slug)

    scraper.fetch_page_js = fetch_page_js
    scraper.fetch_page = fetch_page
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    events = scraper.scrape()
    return events, requested


@pytest.mark.unit
def test_parses_card_and_detail(mock_geocoding_service):
    when = _when(10)
    events, _ = _run(
        {1: _listing([_card('carmen-jones-x', 'Carmen Jones', when)])},
        {'carmen-jones-x': _detail(description='Dandridge stars.')},
    )

    assert len(events) == 1
    e = events[0]
    assert e.title == 'Carmen Jones'
    assert e.event_date == when
    assert e.url == 'https://www.cinema.ucla.edu/events/carmen-jones-x/'
    assert e.image_url == 'https://img.example/carmen-jones-x.jpg'
    assert e.category == 'Film'
    assert e.description == 'Dorothy Dandridge. Dandridge stars.'
    assert e.is_free and e.price is None
    assert e.venue_name == 'Billy Wilder Theater'
    assert e.address == '10899 Wilshire Blvd, Los Angeles, CA 90024'
    assert e.region == 'westside'


@pytest.mark.unit
def test_paid_ticket_price_and_unreachable_detail(mock_geocoding_service):
    cards = [_card('paid-x', 'Paid Show', _when(3)), _card('nodetail-x', 'No Detail', _when(4))]

    events, _ = _run(
        {1: _listing(cards)},
        {'paid-x': _detail(tickets=('General admission: $15', 'Students: $10'))},
    )
    paid, nodetail = events

    assert paid.price == 10.0 and not paid.is_free  # cheapest stated price
    # An unreachable event page still yields an event from the card.
    assert nodetail.title == 'No Detail' and nodetail.venue_name == 'Billy Wilder Theater'
    assert nodetail.price is None and not nodetail.is_free


@pytest.mark.unit
def test_walks_pages_and_stops_at_a_short_page(mock_geocoding_service):
    page1 = [_card(f's{i}-x', f'Film {i}', _when(i + 1)) for i in range(10)]
    page2 = [_card('last-x', 'Last Film', _when(20))]

    events, requested = _run({1: _listing(page1, pages=2), 2: _listing(page2, pages=2)})

    assert len(events) == 11
    assert requested == [
        'https://www.cinema.ucla.edu/events/',
        'https://www.cinema.ucla.edu/events/?page=2',
    ]


@pytest.mark.unit
def test_drops_past_events(mock_geocoding_service):
    now = datetime.now()
    past = _card('past-x', 'Earlier', now - timedelta(days=1))
    future = _card('future-x', 'Later', now + timedelta(days=2))

    events, _ = _run({1: _listing([past, future])})

    assert [e.title for e in events] == ['Later']


@pytest.mark.unit
def test_other_venue_is_not_given_billy_wilder_details(mock_geocoding_service):
    events, _ = _run(
        {1: _listing([_card('away-x', 'Away Game', _when(5))])},
        {'away-x': _detail(venue='Silent Movie Theatre')},
    )
    # Not at Billy Wilder: no borrowed venue, address or coordinates. (Whether
    # the event survives depends on geocoding the stated venue.)
    for e in events:
        assert e.venue_name != 'Billy Wilder Theater'
        assert e.address != '10899 Wilshire Blvd, Los Angeles, CA 90024'


@pytest.mark.unit
@pytest.mark.parametrize('pages', [
    {1: '<html><body><p>Nothing here</p></body></html>'},
    {1: None},
    {1: '<li class="list-item"><a class="title">No link target</a></li>'},
])
def test_empty_or_unrecognised_listing(mock_geocoding_service, pages):
    assert _run(pages)[0] == []


@pytest.mark.unit
def test_undated_card_is_skipped(mock_geocoding_service):
    cards = [_card('x-x', 'Mystery', _when(3), date_text='TBA'), _card('ok-x', 'Dated', _when(4))]

    events, _ = _run({1: _listing(cards)})

    assert [e.title for e in events] == ['Dated']


@pytest.mark.unit
def test_listing_budget_is_checked_after_each_render(mock_geocoding_service, monkeypatch):
    # Fake clock: every render takes 30 s, the budget is 40 s. The first render
    # ends at 30 s (under budget), the second at 60 s (over): no third render.
    clock = {'now': 0.0}
    monkeypatch.setattr('src.scrapers.ucla_film_archive.time.monotonic', lambda: clock['now'])
    pages = {
        n: _listing([_card(f'p{n}-{i}-x', f'Film {n}-{i}', _when(n * 10 + i + 1)) for i in range(10)], pages=5)
        for n in range(1, 6)
    }
    scraper = UCLAFilmArchiveScraper()
    requested = []

    def fetch_page_js(url, wait_selector=None, timeout=30000):
        requested.append((url, timeout))
        clock['now'] += 30
        number = int(url.split('page=')[1].rstrip('/')) if 'page=' in url else 1
        return pages[number]

    scraper.fetch_page_js = fetch_page_js
    scraper.fetch_page = lambda url, retry=3: None
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    events = scraper.scrape()

    assert len(requested) == 2
    assert all(timeout == 15000 for _, timeout in requested)
    assert len(events) == 20  # both rendered pages are still used
