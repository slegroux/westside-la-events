"""
Unit tests for the Unlikely Collaborators (Spark Salons) scraper.
"""
from datetime import datetime, timedelta

import pytest

from src.scrapers.unlikely_collaborators import UnlikelyCollaboratorsScraper


def _home_html():
    # Salons are linked as /home/<speaker-slug>. The site used to use
    # /spark-salon-<slug> and this fixture still emitted that after the scraper
    # moved on, so link discovery found nothing: test_parses_upcoming_salon
    # failed, and test_skips_past_salon passed *vacuously* -- asserting an empty
    # result is trivially true when zero candidates are discovered. Keep the
    # legacy-shaped link here too, so the discovery pattern staying specific to
    # /home/ is itself covered.
    return (
        '<html><body>'
        '<a href="/home/test-speaker">Salon</a>'
        '<a href="/spark-salon-speaker-series">Series overview (not a salon)</a>'
        '</body></html>'
    )


def _salon_html(date_text):
    return f"""
    <html>
      <head>
        <meta property="og:image"
              content="http://static1.squarespace.com/x/main.jpg?format=1500w"/>
      </head>
      <body>
        <p>{date_text}</p>
        <h1>The Nature of Testing</h1>
        <h2>Dr. Test Speaker</h2>
        <p>Attendance is Complimentary. Registration is Required.</p>
        <p>This is a substantial talk description about perception and reality
           that should be captured as the event description shown on the card.</p>
        <p>6:00 p.m.: Doors open, reception</p>
        <h3>Bio</h3>
        <p>Dr. Test Speaker is a researcher who should not appear first.</p>
      </body>
    </html>
    """

def _run(scraper, salon_html):
    scraper.prefetch_pages = lambda urls, max_concurrent=5: None
    scraper.fetch_page = lambda url, retry=3: (
        _home_html() if url == scraper.BASE_URL else salon_html
    )
    return scraper.scrape()


@pytest.mark.unit
def test_parses_upcoming_salon(mock_geocoding_service):
    """An upcoming salon page becomes a free Community event at the SM venue."""
    when = datetime.now() + timedelta(days=14)
    date_text = when.strftime("%A, %B %d, %Y | 7:00pm PT")

    events = _run(UnlikelyCollaboratorsScraper(), _salon_html(date_text))

    assert len(events) == 1
    e = events[0]
    # Talk title gets the speaker appended.
    assert e.title == "The Nature of Testing — Dr. Test Speaker"
    assert e.event_date.hour == 19 and e.event_date.date() == when.date()
    assert e.is_free is True
    assert e.category == "Community"
    assert e.venue_name == "Unlikely Collaborators"
    assert abs(e.latitude - 34.0129862) < 1e-6
    assert abs(e.longitude - (-118.4952006)) < 1e-6
    # Boilerplate/bio stripped; the talk description leads, normalized to https.
    assert "substantial talk description" in e.description
    assert "Complimentary" not in e.description
    assert e.image_url.startswith("https://")


@pytest.mark.unit
def test_skips_past_salon(mock_geocoding_service):
    """A past-dated salon (still linked from the homepage) is dropped."""
    when = datetime.now() - timedelta(days=30)
    date_text = when.strftime("%A, %B %d, %Y | 7:00pm PT")

    events = _run(UnlikelyCollaboratorsScraper(), _salon_html(date_text))

    assert events == []
