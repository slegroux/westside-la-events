"""Unit tests for root site files, share/SEO tags, gzip and the footer source count."""
import pytest
from fastcore.xml import to_xml
from httpx import AsyncClient, ASGITransport

import config
from src.web.app import app
from src.web.components import page_footer, page_head


@pytest.mark.unit
class TestSiteFiles:
    @pytest.mark.asyncio
    async def test_robots_and_sitemap(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://t') as c:
            robots = await c.get('/robots.txt')
            sitemap = await c.get('/sitemap.xml')
        assert robots.status_code == 200
        assert 'Disallow: /admin/' in robots.text
        assert f'Sitemap: {config.SITE_URL}/sitemap.xml' in robots.text
        assert sitemap.status_code == 200
        assert f'<loc>{config.SITE_URL}/</loc>' in sitemap.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize('path,magic', [
        ('/favicon.ico', b'\x00\x00\x01\x00'),
        ('/apple-touch-icon.png', b'\x89PNG'),
    ])
    async def test_root_icons(self, path, magic):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://t') as c:
            r = await c.get(path)
        assert r.status_code == 200
        assert r.content.startswith(magic)

    @pytest.mark.asyncio
    async def test_large_responses_are_gzipped(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://t') as c:
            r = await c.get('/static/css/style.css', headers={'Accept-Encoding': 'gzip'})
        assert r.status_code == 200
        assert r.headers.get('content-encoding') == 'gzip'


@pytest.mark.unit
class TestShareTags:
    def test_canonical_and_social_tags(self):
        html = to_xml(page_head('Westside LA Events', canonical_path='/'))
        assert f'<link rel="canonical" href="{config.SITE_URL}/">' in html
        assert f'content="{config.SITE_URL}/"' in html
        assert 'property="og:image"' in html and 'twitter:card' in html

    def test_error_pages_have_no_canonical(self):
        html = to_xml(page_head('Page Not Found'))
        assert 'rel="canonical"' not in html and 'og:url' not in html


@pytest.mark.unit
class TestFooterSourceCount:
    def test_counts_sources_beyond_the_three_named(self):
        assert '54 more sources' in to_xml(page_footer(source_count=57))

    def test_generic_without_a_count(self):
        html = to_xml(page_footer())
        assert 'many more sources' in html and '30+' not in html
