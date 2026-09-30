"""LogoScraper must never cache a non-image as a logo."""
from unittest.mock import MagicMock

import pytest

from src.utils.logo_scraper import LogoScraper, looks_like_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


@pytest.mark.parametrize("data", [
    PNG,
    b"\xff\xd8\xff\xe0" + b"\0" * 16,
    b"GIF89a" + b"\0" * 16,
    b"\0\0\1\0\1\0\x10\x10",
    b"RIFF\x10\0\0\0WEBPVP8 ",
    b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
    b'<?xml version="1.0"?>\n<svg viewBox="0 0 1 1"></svg>',
])
def test_images_are_recognised(data):
    assert looks_like_image(data)


@pytest.mark.parametrize("data", [
    b"",
    b"<!DOCTYPE html><html><title>Wikimedia Error</title></html>",
    b"<?xml version=\"1.0\"?><rss></rss>",
    b"Not Found",
])
def test_non_images_are_rejected(data):
    assert not looks_like_image(data)


def test_a_mocked_response_body_is_not_an_image():
    # Scraper tests mock the HTTP session; a MagicMock's methods return truthy
    # mocks, which once let download_logo write empty logo files.
    assert not looks_like_image(MagicMock())


@pytest.fixture
def scraper(tmp_path, monkeypatch):
    s = LogoScraper(cache_dir=str(tmp_path))
    monkeypatch.setattr(s, "get_logo_url", lambda source: "https://example.com/logo.png")
    return s


def _respond(scraper, content):
    response = MagicMock(content=content, headers={"Content-Type": "text/html"})
    response.raise_for_status.return_value = None
    scraper.session = MagicMock()
    scraper.session.get.return_value = response


def test_download_refuses_an_html_page(scraper, tmp_path):
    _respond(scraper, b"<!doctype html><html></html>")
    assert scraper.download_logo("Some Venue") is None
    assert list(tmp_path.iterdir()) == []


def test_download_saves_a_real_image(scraper, tmp_path):
    _respond(scraper, PNG)
    assert scraper.download_logo("Some Venue") == "/static/logos/some_venue.png"
    assert (tmp_path / "some_venue.png").read_bytes() == PNG


def test_a_broken_cached_logo_is_replaced(scraper, tmp_path):
    (tmp_path / "some_venue.png").write_bytes(b"")
    _respond(scraper, PNG)
    assert scraper.download_logo("Some Venue") == "/static/logos/some_venue.png"
    assert (tmp_path / "some_venue.png").read_bytes() == PNG
