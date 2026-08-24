"""
Tests for retiring events a source has stopped listing.

Nothing used to remove an event once it was stored, so a listing that vanished
from its source stayed forever. One Oktoberfest listing reached prod 14 times
over -- each run added a copy under a new date and none were retired.
"""
from datetime import datetime, timedelta

import pytest

from src.data.models import Event


def _event(title, source='Test Source', days_ahead=7, url=None):
    return Event(
        title=title,
        venue_name='Somewhere',
        address='123 Main St, Santa Monica, CA',
        latitude=34.0195,
        longitude=-118.4912,
        event_date=datetime.now() + timedelta(days=days_ahead),
        source=source,
        url=url or f'https://example.com/{title.replace(" ", "-")}',
    )


@pytest.mark.unit
class TestPruneStaleEvents:
    def test_removes_future_events_the_scrape_no_longer_lists(self, db):
        kept, _ = db.insert_event(_event('Still Listed'))
        db.insert_event(_event('Dropped From Source'))

        removed = db.prune_stale_events('Test Source', {kept})

        assert removed == 1
        titles = [e.title for e in db.search_events(sources=['Test Source'])]
        assert titles == ['Still Listed']

    def test_leaves_past_events_alone(self, db):
        """Past events are the archive, not stale listings."""
        db.insert_event(_event('Last Month', days_ahead=-30))
        kept, _ = db.insert_event(_event('Upcoming'))

        assert db.prune_stale_events('Test Source', {kept}) == 0

    def test_only_touches_the_named_source(self, db):
        db.insert_event(_event('Other Source Event', source='Another Source'))
        kept, _ = db.insert_event(_event('Kept'))

        db.prune_stale_events('Test Source', {kept})

        others = db.search_events(sources=['Another Source'])
        assert [e.title for e in others] == ['Other Source Event']

    def test_empty_keep_set_clears_the_source(self, db):
        """Callers must gate this; the method itself honours what it is told."""
        db.insert_event(_event('Anything'))
        assert db.prune_stale_events('Test Source', set()) == 1

    def test_no_stale_rows_is_a_no_op(self, db):
        kept, _ = db.insert_event(_event('Only One'))
        assert db.prune_stale_events('Test Source', {kept}) == 0

    def test_handles_more_rows_than_the_sqlite_variable_limit(self, db):
        """Deletion is chunked; verify a large batch actually clears."""
        for index in range(600):
            db.insert_event(_event(f'Event {index}', days_ahead=index % 200 + 1))

        removed = db.prune_stale_events('Test Source', set())

        assert removed == 600
        assert db.search_events(sources=['Test Source']) == []


@pytest.mark.unit
class TestRunnerGuards:
    """A scrape that returns nothing must never be treated as authoritative."""

    def test_empty_result_does_not_make_a_source_prunable(self):
        from run_scrapers import ScraperResult, insert_events_to_db

        class FakeDB:
            def __init__(self):
                self.pruned = []

            def insert_event(self, event):
                return 1, False

            def prune_stale_events(self, source, keep_ids):
                self.pruned.append(source)
                return 0

        empty = ScraperResult('some_scraper')
        empty.events = []

        db = FakeDB()
        insert_events_to_db(db, [empty])

        assert db.pruned == []

    def test_failed_result_does_not_make_a_source_prunable(self):
        from run_scrapers import ScraperResult, insert_events_to_db

        class FakeDB:
            def __init__(self):
                self.pruned = []

            def insert_event(self, event):
                return 1, False

            def prune_stale_events(self, source, keep_ids):
                self.pruned.append(source)
                return 0

        failed = ScraperResult('some_scraper')
        failed.events = [_event('Should Not Count')]
        failed.error = 'timed out'

        db = FakeDB()
        insert_events_to_db(db, [failed])

        assert db.pruned == []

    def test_productive_result_prunes_its_own_source(self):
        from run_scrapers import ScraperResult, insert_events_to_db

        class FakeDB:
            def __init__(self):
                self.pruned = {}
                self.next_id = 100

            def insert_event(self, event):
                self.next_id += 1
                return self.next_id, False

            def prune_stale_events(self, source, keep_ids):
                self.pruned[source] = set(keep_ids)
                return 0

        result = ScraperResult('some_scraper')
        result.events = [_event('Real Event', source='Fairmont Miramar')]

        db = FakeDB()
        insert_events_to_db(db, [result])

        assert set(db.pruned) == {'Fairmont Miramar'}
        assert db.pruned['Fairmont Miramar'] == {101}


@pytest.mark.unit
class TestSharedUrlDoesNotCollapseDifferentEvents:
    """Venues publish a whole week's programme under one page URL."""

    def test_different_titles_under_one_url_stay_separate(self, db):
        page = 'https://www.thevictorian.com/what-s-on'
        friday = _event('WEEKEND KICK OFF', source='The Victorian', url=page)
        friday.event_date = datetime(2026, 8, 28, 20, 0)
        saturday = _event('SIGNATURE SATURDAYS', source='The Victorian', url=page)
        saturday.event_date = datetime(2026, 8, 29, 16, 0)  # 20 hours later

        db.insert_event(friday)
        _, was_duplicate = db.insert_event(saturday)

        assert was_duplicate is False
        titles = {e.title for e in db.search_events(sources=['The Victorian'])}
        assert titles == {'WEEKEND KICK OFF', 'SIGNATURE SATURDAYS'}

    def test_same_title_under_one_url_still_collapses(self, db):
        """The URL rule must still catch a genuine re-listing."""
        page = 'https://example.com/whats-on'
        first = _event('Jazz Night', url=page)
        first.event_date = datetime(2026, 8, 28, 20, 0)
        again = _event('Jazz Night', url=page)
        again.event_date = datetime(2026, 8, 28, 21, 0)

        db.insert_event(first)
        _, was_duplicate = db.insert_event(again)

        assert was_duplicate is True

    def test_recurring_occurrences_under_one_url_stay_separate(self, db):
        """Same title, a week apart -- distinct occurrences, not duplicates."""
        page = 'https://example.com/whats-on'
        week1 = _event('Salsa Thursdays', url=page)
        week1.event_date = datetime(2026, 8, 27, 17, 0)
        week2 = _event('Salsa Thursdays', url=page)
        week2.event_date = datetime(2026, 9, 3, 17, 0)

        db.insert_event(week1)
        _, was_duplicate = db.insert_event(week2)

        assert was_duplicate is False
