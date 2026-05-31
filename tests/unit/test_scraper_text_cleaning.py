"""
Unit tests for clean_scraped_text in src.scrapers.base.

Some sources emit JS/JSON-escaped strings, leaving a literal backslash before
apostrophes/quotes in stored text (e.g. ``Farmers\\' Market``). The cleaner
unescapes those and trims whitespace. Pure function — no network/browser.
"""
import pytest

from src.scrapers.base import clean_scraped_text


@pytest.mark.unit
class TestCleanScrapedText:
    def test_unescapes_apostrophe(self):
        assert clean_scraped_text("Farmers\\' Market") == "Farmers' Market"

    def test_unescapes_double_quote(self):
        assert clean_scraped_text('He said \\"hi\\"') == 'He said "hi"'

    def test_none_and_empty_become_empty_string(self):
        assert clean_scraped_text(None) == ""
        assert clean_scraped_text("") == ""

    def test_strips_surrounding_whitespace(self):
        assert clean_scraped_text("  Jazz Night  ") == "Jazz Night"

    def test_plain_text_unchanged(self):
        assert clean_scraped_text("Santa Monica Pier") == "Santa Monica Pier"

    def test_real_apostrophe_preserved(self):
        # A genuine apostrophe (no backslash) must pass through untouched.
        assert clean_scraped_text("McCabe's Guitar Shop") == "McCabe's Guitar Shop"
