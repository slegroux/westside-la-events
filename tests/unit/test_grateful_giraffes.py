"""
Unit tests for the Grateful Giraffes (The Oasis) scraper.

Fully offline: ``_fetch_events`` is monkeypatched to return base44-shaped
entity records, so no network call is made.

The scraper's own geocoding stub is installed per-test rather than using the
shared ``mock_geocoding_service`` fixture. That fixture matches "los angeles"
before "venice", so the real-world address this source produces for a Venice
event -- "Venice, Los Angeles" -- would resolve to downtown and be filtered
out, testing the fixture's substring order rather than this scraper.
"""
from datetime import date, datetime, timedelta

import pytest

from src.scrapers.grateful_giraffes import GratefulGiraffesScraper


# Coordinates keyed by the most specific place name in the address.
_PLACES = (
    ('venice', (33.9850, -118.4695)),
    ('marina del rey', (33.9802, -118.4517)),
    ('beverly hills', (34.0736, -118.4004)),
    ('colombia', (4.8133, -75.6961)),
    # Bare "Los Angeles" lands downtown, outside the Westside box -- which is
    # exactly what the real geocoder does with a city-only address.
    ('los angeles', (34.0522, -118.2437)),
)


class _Geocoder:
    """Resolve a test address to the most specific place it names."""

    def geocode_with_fallback(self, address, venue_name=None):
        text = (address or '').lower()
        for name, coords in _PLACES:
            if name in text:
                return coords
        return None

    def geocode(self, address):
        return self.geocode_with_fallback(address)


def _record(**overrides):
    """A listable, in-person, future Venice event; override to vary it."""
    record = {
        'title': 'The AI Salon',
        'description': 'An evening of conversation.',
        'date': (date.today() + timedelta(days=3)).isoformat(),
        'time': '7:00 PM',
        'end_time': '9:00 PM',
        'city': 'Los Angeles',
        'town_or_neighborhood': 'Venice',
        'street_address': None,
        'address_hidden': True,
        'venue_host': 'Sawubona',
        'organizer': 'Grateful Giraffes',
        'slug': 'ai-salon',
        'image_url': 'https://media.base44.com/images/public/x/a.png',
        'price': 0.0,
        'tags': [],
        'status': 'active',
        'is_hidden': False,
        'is_public': True,
        'is_sample': False,
        'access_level': 'open',
        'event_type': 'in_person',
    }
    record.update(overrides)
    return record


def _run(records):
    scraper = GratefulGiraffesScraper()
    scraper.geocoding_service = _Geocoder()
    scraper._fetch_events = lambda: records
    return scraper.scrape()


@pytest.mark.unit
def test_parses_a_westside_event():
    """A Venice event parses with time, end time, venue, permalink and price."""
    events = _run([_record()])

    assert len(events) == 1
    event = events[0]
    assert event.title == 'The AI Salon'
    assert event.event_date.hour == 19 and event.event_date.minute == 0
    assert event.end_date.hour == 21
    assert event.venue_name == 'Sawubona'
    assert event.url == 'https://app.grateful.gg/ai-salon'
    assert event.is_free is True
    assert event.price == 0.0
    # Address is built from the parts the record actually publishes.
    assert event.address == 'Venice, Los Angeles'


@pytest.mark.unit
def test_drops_events_with_no_resolvable_location():
    """A city-only address must not be pinned at the city centre."""
    events = _run([_record(town_or_neighborhood=None, slug='eog')])
    assert events == []


@pytest.mark.unit
@pytest.mark.parametrize('overrides', [
    {'status': 'cancelled'},
    {'is_hidden': True},
    {'is_public': False},
    {'is_sample': True},
    {'access_level': 'invite_only'},
    {'event_type': 'virtual'},
], ids=['inactive', 'hidden', 'not-public', 'sample', 'invite-only', 'virtual'])
def test_skips_records_the_site_does_not_list(overrides):
    """Visibility flags mirror what a visitor actually sees on /events."""
    assert _run([_record(**overrides)]) == []


@pytest.mark.unit
def test_keeps_giraffes_only_events():
    """giraffes_only is a members' event but is listed publicly, so keep it."""
    events = _run([_record(access_level='giraffes_only')])
    assert len(events) == 1


@pytest.mark.unit
def test_skips_past_events():
    past = (date.today() - timedelta(days=1)).isoformat()
    assert _run([_record(date=past)]) == []


@pytest.mark.unit
def test_keeps_an_event_happening_today():
    events = _run([_record(date=date.today().isoformat())])
    assert len(events) == 1


@pytest.mark.unit
def test_drops_out_of_area_events():
    """The retreat in Colombia is in the same feed as the LA gatherings."""
    events = _run([_record(city='Pereira, Colombia',
                           town_or_neighborhood=None, slug='ggretreat')])
    assert events == []


@pytest.mark.unit
@pytest.mark.parametrize('raw,expected', [
    ('7:00 PM', (19, 0)),
    ('6:30pm', (18, 30)),
    ('9:00 AM', (9, 0)),
    ('9:00 AM PST', (9, 0)),
    ('12:00 PM', (12, 0)),
    ('12:00 AM', (0, 0)),
    # The colon is missing in one real record.
    ('300PM', (15, 0)),
    ('17:30', (17, 30)),
    ('09:00', (9, 0)),
])
def test_parses_the_hand_entered_time_formats(raw, expected):
    assert GratefulGiraffesScraper()._parse_time(raw) == expected


@pytest.mark.unit
@pytest.mark.parametrize('raw', [
    'Sunday afternoon',  # real end_time value in the feed
    '', None, 'noon', '25:00', '7:99 PM', '13:00 PM',
])
def test_rejects_times_that_are_not_clock_times(raw):
    """An unreadable time must not be guessed at."""
    assert GratefulGiraffesScraper()._parse_time(raw) is None


@pytest.mark.unit
def test_missing_time_falls_back_to_midnight():
    """The date is the reliable half; the site lists some events with no time."""
    events = _run([_record(time=None, end_time=None)])
    assert len(events) == 1
    assert events[0].event_date.hour == 0
    assert events[0].end_date is None


@pytest.mark.unit
def test_end_time_before_start_is_dropped():
    """'7:00 PM' -> '1:00 AM' runs past midnight, which the feed cannot express."""
    events = _run([_record(time='7:00 PM', end_time='1:00 AM')])
    assert len(events) == 1
    assert events[0].end_date is None


@pytest.mark.unit
@pytest.mark.parametrize('placeholder', [
    'Register to See Address',
    'Register to See AAd animaddress',  # corrupted variant in the live feed
])
def test_rsvp_placeholder_is_not_used_as_a_venue(placeholder):
    events = _run([_record(venue_host=placeholder)])
    assert len(events) == 1
    assert events[0].venue_name == 'Grateful Giraffes'


@pytest.mark.unit
def test_venue_falls_back_to_source_name_without_a_host_or_organizer():
    events = _run([_record(venue_host=None, organizer=None)])
    assert len(events) == 1
    assert events[0].venue_name == 'Grateful Giraffes'


@pytest.mark.unit
def test_published_street_address_is_included():
    events = _run([_record(street_address='Primal Moves',
                           town_or_neighborhood='Marina Del Rey',
                           address_hidden=False)])
    assert len(events) == 1
    assert events[0].address == 'Primal Moves, Marina Del Rey, Los Angeles'


@pytest.mark.unit
def test_hidden_street_address_is_withheld():
    """address_hidden means the street line is not ours to publish."""
    events = _run([_record(street_address='123 Secret Way',
                           address_hidden=True)])
    assert len(events) == 1
    assert '123 Secret Way' not in events[0].address


@pytest.mark.unit
def test_neighbourhood_equal_to_city_is_not_repeated():
    events = _run([_record(city='Beverly Hills',
                           town_or_neighborhood='Beverly Hills')])
    assert len(events) == 1
    assert events[0].address == 'Beverly Hills'


@pytest.mark.unit
@pytest.mark.parametrize('price,expected_price,expected_free', [
    (0.0, 0.0, True),
    (60.0, 60.0, False),
    (100, 100.0, False),
    (None, None, False),
])
def test_price_and_free_flag(price, expected_price, expected_free):
    events = _run([_record(price=price)])
    assert len(events) == 1
    assert events[0].price == expected_price
    assert events[0].is_free is expected_free


@pytest.mark.unit
def test_no_price_note_is_emitted():
    """Project convention: an unknown price renders no badge, never 'TBD'."""
    events = _run([_record(price=None)])
    assert events[0].price_note == ''


@pytest.mark.unit
@pytest.mark.parametrize('title,tags,expected', [
    ('The AI Salon', [], 'Community'),
    ('The Joy of Gratitude', [], 'Community'),
    ('Cosmic Concert: Immersive Soundscape', [], 'Music'),
    ('AI Bootcamp · September 26-27', [], 'Education'),
    ('Biohacking Safari', ['safari', 'biohacking'], 'Wellness'),
    ('Sunset Sound Bath', [], 'Wellness'),
    ('Giraffe Potluck', [], 'Food'),
])
def test_category_mapping(title, tags, expected):
    events = _run([_record(title=title, tags=tags)])
    assert len(events) == 1
    assert events[0].category == expected


@pytest.mark.unit
def test_slugless_record_links_to_the_listing_page():
    """A third of the feed has no slug and so has no permalink of its own."""
    events = _run([_record(slug=None)])
    assert events[0].url == 'https://app.grateful.gg/events'


@pytest.mark.unit
def test_image_falls_back_through_the_available_fields():
    events = _run([_record(image_url=None, cover_photo_url=None,
                           og_image_url='https://example.com/og.png')])
    assert events[0].image_url == 'https://example.com/og.png'


@pytest.mark.unit
def test_survives_a_malformed_record_without_losing_the_rest():
    """One bad record must not take the whole scrape down."""
    events = _run([{'title': 'Broken'}, _record()])
    assert len(events) == 1
    assert events[0].title == 'The AI Salon'


@pytest.mark.unit
def test_empty_api_response_yields_no_events():
    assert _run([]) == []


@pytest.mark.unit
def test_fetch_events_handles_a_bare_json_array(monkeypatch):
    """The endpoint returns a list, not the dict fetch_json is typed for."""
    scraper = GratefulGiraffesScraper()
    monkeypatch.setattr(scraper, 'fetch_json',
                        lambda *a, **k: [{'title': 'a'}, 'not-a-dict'])
    assert scraper._fetch_events() == [{'title': 'a'}]


@pytest.mark.unit
def test_fetch_events_returns_empty_on_failure(monkeypatch):
    scraper = GratefulGiraffesScraper()
    monkeypatch.setattr(scraper, 'fetch_json', lambda *a, **k: None)
    assert scraper._fetch_events() == []
