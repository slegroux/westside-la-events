"""
Unit tests for Arcana Books scraper.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.arcana_books import ArcanaBooksScraper


@pytest.mark.unit
def test_arcana_books_scraper_parses_upcoming_event(mock_geocoding_service):
    """Scraper should parse an upcoming event post into an Event."""
    target_date = datetime.now() + timedelta(days=7)
    date_text = target_date.strftime("%B %d, %Y, 6:00 PM")

    html = f"""
    <html>
      <body>
        <div class="blog-item">
          <div class="blog-info">
            <h1 class="blog-title"><a href="/blog/upcoming-signing">Upcoming Signing Night</a></h1>
            <div class="blog-excerpt">
              <p>Join us on {date_text} at Arcana for an artist talk.</p>
            </div>
          </div>
          <img src="/images/event.jpg" />
        </div>
      </body>
    </html>
    """

    scraper = ArcanaBooksScraper()
    scraper.geocoding_service.geocode = lambda address: (34.0211, -118.3965)
    scraper.fetch_page = lambda url, retry=3: html
    events = scraper.scrape()

    assert len(events) == 1
    assert events[0].title == "Upcoming Signing Night"
    assert events[0].venue_name == "Arcana: Books on the Arts"
    assert events[0].url.endswith("/blog/upcoming-signing")


@pytest.mark.unit
def test_arcana_books_scraper_skips_past_event(mock_geocoding_service):
    """Scraper should skip historical posts from the events category."""
    target_date = datetime.now() - timedelta(days=365)
    date_text = target_date.strftime("%B %d, %Y, 6:00 PM")

    html = f"""
    <html>
      <body>
        <div class="blog-item">
          <div class="blog-info">
            <h1 class="blog-title"><a href="/blog/past-event">Past Event</a></h1>
            <div class="blog-excerpt"><p>{date_text}</p></div>
          </div>
        </div>
      </body>
    </html>
    """

    scraper = ArcanaBooksScraper()
    scraper.geocoding_service.geocode = lambda address: (34.0211, -118.3965)
    scraper.fetch_page = lambda url, retry=3: html
    events = scraper.scrape()

    assert events == []
