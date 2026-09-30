"""
Unit tests for the logo lockup, home hero, and the shared List/Map toggle.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastcore.xml import to_xml
from httpx import AsyncClient, ASGITransport

from src.web.app import app, state
from src.web.components import brand_lockup, home_hero, view_toggle

STATIC = Path(__file__).resolve().parents[2] / 'static'


@pytest.mark.unit
class TestBrandAssets:
    @pytest.mark.parametrize('path', ['images/logo.svg', 'favicon.svg'])
    def test_logo_svg_parses(self, path):
        root = ET.parse(STATIC / path).getroot()
        assert root.tag.endswith('svg')
        assert root.get('viewBox') == '0 0 64 64'

    def test_apple_touch_icon_is_png(self):
        data = (STATIC / 'images/apple-touch-icon.png').read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'

    def test_lockup_keeps_full_name_as_text(self):
        html = to_xml(brand_lockup())
        assert '/static/images/logo.svg' in html
        assert 'Westside' in html and 'LA Events' in html
        assert 'href="/"' in html


@pytest.mark.unit
class TestHomeHero:
    def test_renders_counts_and_quick_filters(self):
        html = to_xml(home_hero(total_count=1277, today_count=68, source_count=57))
        assert '1,277' in html and '68' in html and '57' in html
        for key in ('weekend', 'free', 'family', 'date-night'):
            assert f"applyQuickFilter('{key}')" in html

    def test_omits_stats_without_counts(self):
        assert 'hero-stats' not in to_xml(home_hero())


@pytest.mark.unit
class TestViewToggle:
    @pytest.mark.parametrize('active', ['list', 'map'])
    def test_active_state(self, active):
        html = to_xml(view_toggle(active))
        other = 'map' if active == 'list' else 'list'
        assert f'id="{active}-view-btn" class="view-btn active"' in html
        assert f'id="{other}-view-btn" class="view-btn"' in html

    def test_buttons_carry_the_filter_form(self):
        # Regression: the OOB copies used hx-include=".search-section", a
        # selector no longer on the page, so filters were dropped after the
        # first List/Map switch.
        html = to_xml(view_toggle('map', oob=True))
        assert html.count('hx-include="closest form, #header-search"') == 2
        assert '.search-section' not in html
        assert 'hx-swap-oob="true"' in html


@pytest.mark.unit
@pytest.mark.asyncio
class TestPagesUseSharedPieces:
    async def test_home_has_hero_logo_and_favicon(self, populated_db, monkeypatch):
        from src.search.query import EventSearch
        monkeypatch.setattr(state, 'db', populated_db)
        monkeypatch.setattr(state, 'search', EventSearch(populated_db))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert 'class="home-hero"' in response.text
        assert '/static/images/logo.svg' in response.text
        assert 'href="/static/favicon.svg"' in response.text

    @pytest.mark.parametrize('view', ['list', 'map'])
    async def test_view_swaps_keep_filters(self, populated_db, view, monkeypatch):
        from src.search.query import EventSearch
        monkeypatch.setattr(state, 'db', populated_db)
        monkeypatch.setattr(state, 'search', EventSearch(populated_db))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/view/{view}")
        assert response.status_code == 200
        assert response.text.count('hx-include="closest form, #header-search"') == 2
        assert '.search-section' not in response.text
