"""
Unit tests for _is_hero_image in src.web.components.

A source *logo* must never be used as a card's hero image — otherwise the same
graphic tiles across every card from that source (e.g. Shore Hotel). Such cards
fall back to the per-category gradient placeholder instead.
"""
import pytest

from src.data.models import Event
from src.web.components import (
    _is_hero_image,
    _placeholder_image,
    _CATEGORY_THEME,
    _STOCK_THEMES,
)


@pytest.mark.unit
class TestIsHeroImage:
    def test_real_remote_photo_is_hero(self):
        event = Event(
            title='Concert',
            image_url='https://cdn.example.com/photos/show.jpg',
            source_logo_url='/static/logos/example.png',
        )
        assert _is_hero_image(event) is True

    def test_missing_image_is_not_hero(self):
        assert _is_hero_image(Event(title='No image', image_url=None)) is False
        assert _is_hero_image(Event(title='Empty', image_url='')) is False
        assert _is_hero_image(Event(title='Whitespace', image_url='   ')) is False

    def test_image_equal_to_source_logo_is_not_hero(self):
        logo = '/static/logos/shore_hotel.jpg'
        event = Event(title='Farmer market', image_url=logo, source_logo_url=logo)
        assert _is_hero_image(event) is False

    def test_image_under_static_logos_is_not_hero(self):
        # Even when source_logo_url differs, a /static/logos/ path is a logo.
        event = Event(
            title='Aggregated',
            image_url='/static/logos/some_venue.png',
            source_logo_url='/static/logos/other.png',
        )
        assert _is_hero_image(event) is False


@pytest.mark.unit
class TestPlaceholderImage:
    """Themed stock photo chosen for image-less events."""

    def test_returns_themed_stock_path(self):
        path = _placeholder_image(Event(id=1, title='Saturday Market', category='Food'))
        assert path is not None
        # Food maps to the 'food' theme folder.
        assert path.startswith('/static/stock/food/') and path.endswith('.jpg')

    def test_category_variants_map_to_same_theme(self):
        # 'Arts' / 'Art & Museums' are art; 'Food & Drink' is food.
        assert _CATEGORY_THEME['arts'] == 'art'
        assert _CATEGORY_THEME['art & museums'] == 'art'
        assert _CATEGORY_THEME['food & drink'] == 'food'

    def test_unknown_category_falls_back_to_other(self):
        path = _placeholder_image(Event(id=2, title='Mystery', category='Zzz Unknown'))
        assert path is not None
        assert path.startswith('/static/stock/other/')

    def test_deterministic_and_restart_stable(self):
        # Same id+title -> same image every call (crc32, not salted hash()).
        e = Event(id=42, title='Crenshaw Farmers Market', category='Food')
        assert _placeholder_image(e) == _placeholder_image(e)

    def test_varies_across_events_in_same_category(self):
        # A run of same-category events should not all collapse to one image.
        paths = {
            _placeholder_image(Event(id=i, title=f'Market {i}', category='Food'))
            for i in range(12)
        }
        assert len(paths) > 1

    def test_every_theme_has_at_least_one_image(self):
        # Guards against a half-populated stock dir shipping.
        assert _STOCK_THEMES, 'no stock themes loaded'
        for theme, imgs in _STOCK_THEMES.items():
            assert imgs, f'theme {theme} has no images'
