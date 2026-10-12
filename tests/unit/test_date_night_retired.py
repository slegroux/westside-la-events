"""
Tests for retiring the 'Date Night' category.

Every 'Date Night' row was a weekly jazz night: the category's keyword list
('jazz night', 'live jazz', 'rooftop', 'speakeasy', 'cocktail hour') carried
the top weight and pulled jazz out of Music. Date night is now a curated view
(the hero chip), not a category.
"""
from datetime import datetime, timedelta

import pytest

import config
from src.data.models import Event
from src.utils.categories import CategoryClassifier, classify_event, reclassify_retired

@pytest.mark.unit
class TestDateNightRetired:
    def test_not_a_category(self):
        assert 'Date Night' not in config.CATEGORIES
        classifier = CategoryClassifier()
        assert 'Date Night' not in classifier.category_keywords
        assert 'Date Night' not in classifier.category_priorities

    @pytest.mark.parametrize('title, description', [
        ('Jazz Night at the Lobby Bar', 'Live jazz every Thursday'),
        ('Rooftop Jazz', 'Live jazz on the rooftop with a speakeasy cocktail hour'),
    ])
    def test_jazz_nights_stay_in_music(self, title, description):
        assert classify_event(title, description) == 'Music'

    def test_romantic_wording_no_longer_yields_date_night(self):
        assert classify_event('Romantic candlelit dinner for couples') != 'Date Night'


@pytest.mark.unit
class TestReclassifyDateNight:
    def test_moves_rows_out_of_date_night(self, db):
        event = Event(
            title='Jazz Night at the Lobby Bar',
            description='Live jazz every Thursday',
            venue_name='Hotel Lobby',
            event_date=datetime.now() + timedelta(days=3),
            source='Visit Santa Monica',
            url='https://example.com/jazz-night',
            category='Date Night',
        )
        event_id, _ = db.insert_event(event)

        moved = reclassify_retired(db)

        assert dict(moved) == {'Music': 1}
        assert db.get_event(event_id).category == 'Music'
        with db.get_connection() as conn:
            left = conn.execute(
                "SELECT COUNT(*) FROM events WHERE category = 'Date Night'"
            ).fetchone()[0]
        assert left == 0
        # Nothing left to move on the next run.
        assert not reclassify_retired(db)
