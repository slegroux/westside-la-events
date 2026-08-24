"""
Unit tests for the "beyond the Westside" region split.

Events carry a region ('westside' or 'beyond'); the Westside tab must keep
showing exactly what it showed before the column existed, and curated
out-of-area sources must survive the Westside geo-fence while still being held
to LA County.
"""
from datetime import datetime, timedelta

import pytest

from src.data.models import Event
from src.scrapers.base import BaseScraper
from src.utils.geo_filter import (
    is_in_coverage_area,
    is_in_la_county,
    validate_beyond_location,
)


def _event(title, region='westside', days_ahead=1, url=None):
    return Event(
        title=title,
        venue_name='Somewhere',
        address='123 Main St, Santa Monica, CA',
        latitude=34.0195,
        longitude=-118.4912,
        event_date=datetime.now() + timedelta(days=days_ahead),
        source='test',
        url=url or f'https://example.com/{title}',
        region=region,
    )


@pytest.mark.unit
class TestLACountyBounds:
    def test_hollywood_is_in_county_but_not_coverage(self):
        """The whole point of the beyond tab: in LA, outside the Westside box."""
        lat, lng = 34.1016, -118.3410  # Hollywood Roosevelt
        assert is_in_la_county(lat, lng) is True
        assert is_in_coverage_area(lat, lng) is False

    def test_sunset_strip_is_in_county_but_not_coverage(self):
        lat, lng = 34.0941, -118.3756  # 1 Hotel West Hollywood
        assert is_in_la_county(lat, lng) is True
        assert is_in_coverage_area(lat, lng) is False

    def test_westside_is_in_both(self):
        lat, lng = 34.0195, -118.4912  # Santa Monica
        assert is_in_la_county(lat, lng) is True
        assert is_in_coverage_area(lat, lng) is True

    def test_out_of_county_rejected(self):
        assert is_in_la_county(32.7157, -117.1611) is False  # San Diego
        assert validate_beyond_location(32.7157, -117.1611)[0] is False

    def test_unlocated_beyond_event_is_kept(self):
        """Beyond sources are hand-picked, so a missing geocode isn't fatal."""
        ok, reason = validate_beyond_location(None, None, 'Somewhere in LA')
        assert ok is True
        assert reason == 'beyond_source_unlocated'


@pytest.mark.unit
class TestScraperRegion:
    def test_default_region_is_westside(self):
        assert BaseScraper.REGION == 'westside'

    def test_beyond_scraper_keeps_out_of_area_event(self):
        """A 'beyond' scraper's Hollywood event survives the Westside fence."""

        class BeyondScraper(BaseScraper):
            REGION = 'beyond'

            def scrape(self):
                return []

        scraper = BeyondScraper('Test Beyond')
        event = scraper.create_event(
            title='Cabaret in Hollywood',
            venue_name='The Hollywood Roosevelt',
            address='7000 Hollywood Blvd, Los Angeles, CA 90028',
            event_date=datetime.now() + timedelta(days=3),
            latitude=34.1016,
            longitude=-118.3410,
        )
        assert event is not None
        assert event.region == 'beyond'

    def test_westside_scraper_still_drops_out_of_area_event(self):
        """The default region must not become a backdoor into the main tab."""

        class WestsideScraper(BaseScraper):
            def scrape(self):
                return []

        scraper = WestsideScraper('Test Westside')
        event = scraper.create_event(
            title='Cabaret in Hollywood',
            venue_name='The Hollywood Roosevelt',
            address='7000 Hollywood Blvd, Los Angeles, CA 90028',
            event_date=datetime.now() + timedelta(days=3),
            latitude=34.1016,
            longitude=-118.3410,
        )
        assert event is None

    def test_beyond_scraper_drops_out_of_county_event(self):
        class BeyondScraper(BaseScraper):
            REGION = 'beyond'

            def scrape(self):
                return []

        scraper = BeyondScraper('Test Beyond')
        event = scraper.create_event(
            title='Something in San Diego',
            venue_name='Somewhere',
            address='San Diego, CA',
            event_date=datetime.now() + timedelta(days=3),
            latitude=32.7157,
            longitude=-117.1611,
        )
        assert event is None


@pytest.mark.unit
class TestRegionPersistenceAndFiltering:
    def test_region_round_trips_through_the_database(self, db):
        event_id, _ = db.insert_event(_event('Beyond Event', region='beyond'))
        assert db.get_event(event_id).region == 'beyond'

    def test_search_filters_by_region(self, db):
        db.insert_event(_event('Westside Event', region='westside'))
        db.insert_event(_event('Beyond Event', region='beyond'))

        westside = db.search_events(region='westside')
        beyond = db.search_events(region='beyond')

        assert [e.title for e in westside] == ['Westside Event']
        assert [e.title for e in beyond] == ['Beyond Event']

    def test_search_without_region_returns_both(self, db):
        db.insert_event(_event('Westside Event', region='westside'))
        db.insert_event(_event('Beyond Event', region='beyond'))
        assert len(db.search_events()) == 2

    def test_legacy_rows_without_region_show_in_westside(self, db):
        """Rows written before the column existed must not fall out of the app."""
        event_id, _ = db.insert_event(_event('Legacy Event'))
        with db.get_connection() as conn:
            conn.execute('UPDATE events SET region = NULL WHERE id = ?', (event_id,))

        titles = [e.title for e in db.search_events(region='westside')]
        assert 'Legacy Event' in titles


@pytest.mark.unit
class TestRegionSurvivesDeduplication:
    """Re-scraping must not migrate a beyond event into the Westside tab."""

    def test_merge_keeps_primary_region(self):
        from src.utils.deduplication import merge_event_data

        existing = _event('Cabaret', region='beyond')
        existing.id = 7
        incoming = _event('Cabaret', region='beyond')

        merged = merge_event_data(existing, incoming)
        assert merged.region == 'beyond'

    def test_reinsert_does_not_reset_region(self, db):
        """The exact path that stripped region on the nightly re-scrape."""
        event = _event('Cabaret', region='beyond', url='https://example.com/cabaret')
        event_id, was_dup = db.insert_event(event)
        assert was_dup is False

        again = _event('Cabaret', region='beyond', url='https://example.com/cabaret')
        again.event_date = event.event_date
        _, was_dup = db.insert_event(again)
        assert was_dup is True

        assert db.get_event(event_id).region == 'beyond'
