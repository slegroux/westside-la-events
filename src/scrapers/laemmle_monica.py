"""
Scraper for Laemmle Monica Film Center.
Source: https://www.laemmle.com/theater/monica-film-center

Scrapes movie showtimes and information from the Monica Film Center theater page.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import parser as date_parser
import re

from .base import BaseScraper
from src.data.models import Event


class LaemmleMonicaScraper(BaseScraper):
    """Scraper for Laemmle Monica Film Center events."""

    def __init__(self):
        super().__init__('Laemmle Monica Film Center')
        self.base_url = 'https://www.laemmle.com'
        self.theater_url = f'{self.base_url}/theater/monica-film-center'
        self.venue_name = 'Laemmle Monica Film Center'
        self.venue_address = '1332 2nd Street, Santa Monica, CA 90401'

    def scrape(self) -> List[Event]:
        """
        Scrape movie showtimes from Laemmle Monica Film Center.

        Returns:
            List of Event objects (one per movie, not per showtime)
        """
        self.log("Starting scrape...")
        events = []

        try:
            # Fetch the theater page
            html = self.fetch_page(self.theater_url)
            if not html:
                self.log("Failed to fetch theater page")
                return events

            soup = self.parse_html(html)

            # Find all movie containers - they're typically in divs with film info
            # Look for links to /film/ pages which indicate movie cards
            film_links = soup.find_all('a', href=re.compile(r'/film/'))

            # Group by unique film URLs to avoid duplicates
            # Normalize URLs by removing query strings and converting to absolute
            unique_films = {}
            for link in film_links:
                film_url = link.get('href', '')
                if film_url:
                    # Remove query string for uniqueness
                    clean_url = film_url.split('?')[0]
                    # Normalize to absolute URL
                    clean_url = self.normalize_url(clean_url, self.base_url)

                    if clean_url not in unique_films:
                        unique_films[clean_url] = link

            self.log(f"Found {len(unique_films)} unique films")

            # Process each unique film once by fetching its detail page
            for i, film_url in enumerate(unique_films.keys(), 1):
                try:
                    event = self._parse_movie_from_theater_page(soup, film_url)
                    if event:
                        events.append(event)
                        self.log(f"Event {i}/{len(unique_films)}: {event.title}")
                except Exception as e:
                    self.log(f"Error parsing movie at {film_url}: {e}")
                    continue

            self.log(f"Successfully scraped {len(events)} movies")

        except Exception as e:
            self.log(f"Error during scrape: {e}")

        return events

    def _parse_movie_from_theater_page(self, soup, film_url: str) -> Optional[Event]:
        """
        Parse a single movie by fetching its detail page.

        Args:
            soup: BeautifulSoup object of theater page (not used, kept for compatibility)
            film_url: Full URL to the film detail page

        Returns:
            Event object or None
        """
        # Fetch the film detail page to get showtimes
        film_html = self.fetch_page(film_url)
        if not film_html:
            self.log(f"Failed to fetch film detail page: {film_url}")
            return None

        film_soup = self.parse_html(film_html)

        # Extract title from page header
        title_elem = film_soup.find('h1', class_='page-header')
        if not title_elem:
            return None

        title = self.clean_text(title_elem.get_text())
        if not title:
            return None

        # Extract image URL - look for main film poster
        image_url = ''
        # Look for the film poster - Laemmle uses the title as alt text
        img = film_soup.find('img', alt=title)
        if not img:
            # Try to find poster by common patterns
            img = film_soup.find('img', class_=re.compile(r'poster|film-image'))
        if not img:
            # Fallback to any img in the main content that's not the logo
            img = film_soup.find('div', class_='field--name-field-poster-image')
            if img:
                img = img.find('img')
        if img:
            image_url = img.get('src', '')
            # Prefer the original image URL over thumbnails
            if 'styles/' in image_url:
                # Try to find the original image from the src attribute
                original_img = film_soup.find('img', src=re.compile(r'/sites/default/files/images/'))
                if original_img:
                    original_src = original_img.get('src', '')
                    if original_src and '/images/' in original_src:
                        image_url = original_src
            if image_url and not image_url.startswith('http'):
                image_url = self.normalize_url(image_url, self.base_url)

        # Extract runtime and rating (e.g., "118 min. R")
        runtime_rating = ''
        # Look for film details section
        details_section = film_soup.find('div', class_=re.compile(r'film-details|movie-info'))
        if details_section:
            text_content = details_section.get_text()
        else:
            text_content = film_soup.get_text()

        runtime_match = re.search(r'(\d+)\s*min\.?\s*([A-Z\-]+)?', text_content)
        if runtime_match:
            runtime = runtime_match.group(1)
            rating = runtime_match.group(2) if runtime_match.group(2) else 'Not Rated'
            runtime_rating = f"{runtime} min. {rating}"

        # Find the Monica Film Center section with showtimes
        # Look for the div.movie container that contains theater info for Monica
        showtimes = []
        earliest_date = None

        # Find all movie divs (each represents a theater)
        movie_divs = film_soup.find_all('div', class_='movie')

        for movie_div in movie_divs:
            # Check if this is the Monica Film Center
            theater_link = movie_div.find('a', href='/theater/monica-film-center')
            if not theater_link:
                continue

            # Found Monica Film Center section, now extract showtimes
            showtimes_div = movie_div.find('div', class_='showtimes')
            if not showtimes_div:
                continue

            # Find all showtime spans (both past and future)
            showtime_spans = showtimes_div.find_all('span', class_=re.compile(r'showtime'))

            for showtime_span in showtime_spans:
                # Look for time text in nested spans
                time_span = showtime_span.find('span', class_=re.compile(r'showtime-'))
                if not time_span:
                    # Try direct link
                    time_link = showtime_span.find('a')
                    if time_link:
                        showtime_text = self.clean_text(time_link.get_text())
                        ticket_url = time_link.get('href', '')
                    else:
                        continue
                else:
                    showtime_text = self.clean_text(time_span.get_text())
                    # Look for ticket link at span level
                    time_link = showtime_span.find('a')
                    ticket_url = time_link.get('href', '') if time_link else ''

                if showtime_text:
                    # Parse showtime text (e.g., "1:10pm", "7:30pm")
                    try:
                        # Try to parse the time
                        time_match = re.match(r'(\d{1,2}):(\d{2})\s*(am|pm)', showtime_text.lower())
                        if time_match:
                            hour = int(time_match.group(1))
                            minute = int(time_match.group(2))
                            period = time_match.group(3)

                            # Convert to 24-hour format
                            if period == 'pm' and hour != 12:
                                hour += 12
                            elif period == 'am' and hour == 12:
                                hour = 0

                            # Create datetime for today (we'll update if we find date info)
                            now = datetime.now()
                            showtime_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                            # If the showtime is in the past, assume it's for today or tomorrow
                            if showtime_dt < now:
                                showtime_dt = showtime_dt + timedelta(days=1)

                            showtimes.append({
                                'time': showtime_text,
                                'datetime': showtime_dt,
                                'url': ticket_url
                            })

                            # Track earliest showtime
                            if earliest_date is None or showtime_dt < earliest_date:
                                earliest_date = showtime_dt
                    except Exception as e:
                        self.log(f"Error parsing showtime '{showtime_text}': {e}")

            # Break after finding Monica Film Center section
            break

        # Build full movie URL
        full_url = self.normalize_url(film_url, self.base_url)

        # Build description
        description_parts = []

        # Add runtime and rating first
        if runtime_rating:
            description_parts.append(runtime_rating)

        # Add showtimes prominently (will appear right after the calendar icon date/time)
        if showtimes:
            # List showtimes in description
            showtime_list = ', '.join([st['time'] for st in showtimes[:10]])  # Show up to 10 showtimes
            if len(showtimes) > 10:
                showtime_list += f' and {len(showtimes) - 10} more'
            description_parts.append(f"Additional showtimes: {showtime_list}")

        # Add venue context
        description_parts.append(f"Film screening at {self.venue_name}")
        description_parts.append("Independent and art house cinema in Santa Monica")

        # Add call to action
        if not showtimes:
            description_parts.append("Check website for current showtimes")
        else:
            description_parts.append("Visit the website to purchase tickets")

        description = ". ".join(description_parts) + "."

        # Pricing info - Laemmle typically has standard ticket pricing
        # We can't extract exact prices without visiting ticketing pages
        # Leave price_note empty so it displays as $TBD
        price_note = None

        return self.create_event(
            title=title,
            description=description,
            venue_name=self.venue_name,
            address=self.venue_address,
            event_date=earliest_date,
            end_date=None,
            url=full_url,
            image_url=image_url,
            category='Film',  # Use 'Film' category for movies
            price=None,  # Price varies by showtime/day
            is_free=False,
            price_note=price_note
        )
