"""
Unit tests for the Bodega Wine Bar scraper.

Bodega's schedule is transcribed from poster images rather than parsed, so the
tests focus on the guard that stops a stale transcription being published.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.scrapers.bodega_wine_bar import BodegaWineBarScraper


ALL_POSTERS = ''.join(
    f'<img src="{s["poster"]}">' for s in BodegaWineBarScraper.SPECIALS
)


@pytest.mark.unit
class TestBodegaPosterGuard:
    def test_emits_specials_while_posters_are_published(self):
        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value=ALL_POSTERS):
            events = scraper.scrape()

        assert events
        assert {e.title for e in events} == {
            s['title'] for s in BodegaWineBarScraper.SPECIALS
        }

    def test_drops_a_special_whose_poster_is_gone(self):
        """A swapped poster means the transcription can no longer be trusted."""
        dropped = BodegaWineBarScraper.SPECIALS[0]
        html = ''.join(
            f'<img src="{s["poster"]}">'
            for s in BodegaWineBarScraper.SPECIALS
            if s['poster'] != dropped['poster']
        )

        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value=html):
            events = scraper.scrape()

        assert dropped['title'] not in {e.title for e in events}
        assert events, 'the remaining specials should still publish'

    def test_no_posters_means_no_events(self):
        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value='<html></html>'):
            assert scraper.scrape() == []

    def test_unreachable_page_yields_nothing(self):
        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value=None):
            assert scraper.scrape() == []


@pytest.mark.unit
class TestBodegaSchedule:
    def test_occurrences_land_on_the_advertised_weekday(self):
        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value=ALL_POSTERS):
            events = scraper.scrape()

        expected = {s['title']: s['weekday'] for s in BodegaWineBarScraper.SPECIALS}
        for event in events:
            assert event.event_date.weekday() == expected[event.title]

    def test_occurrences_are_in_the_future(self):
        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value=ALL_POSTERS):
            events = scraper.scrape()

        now = datetime.now()
        horizon = now + timedelta(days=BodegaWineBarScraper.LOOKAHEAD_DAYS + 1)
        for event in events:
            assert now <= event.event_date <= horizon

    def test_trivia_starts_at_the_time_on_the_poster(self):
        scraper = BodegaWineBarScraper()
        with patch.object(scraper, 'fetch_page_js', return_value=ALL_POSTERS):
            events = scraper.scrape()

        trivia = [e for e in events if e.title == 'Sunday Trivia Night']
        assert trivia
        for event in trivia:
            assert (event.event_date.hour, event.event_date.minute) == (18, 30)
            assert event.is_free is True
