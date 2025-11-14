"""
Utility functions for generating iCalendar (.ics) files from events.
"""
from datetime import datetime, timedelta
from typing import Optional
from src.data.models import Event


def generate_ics(event: Event) -> str:
    """
    Generate an iCalendar (.ics) file content for an event.

    Args:
        event: Event object to convert to iCalendar format

    Returns:
        String containing the .ics file content
    """
    # Format dates in iCalendar format (YYYYMMDDTHHMMSS)
    def format_ical_date(dt: datetime) -> str:
        """Format a datetime for iCalendar (removes timezone info)."""
        return dt.strftime('%Y%m%dT%H%M%S')

    # Get start and end times
    start_time = event.event_date

    # If end_date exists, use it; otherwise assume 2-hour duration
    if event.end_date:
        end_time = event.end_date
    else:
        end_time = start_time + timedelta(hours=2)

    # Format the timestamps
    dtstart = format_ical_date(start_time)
    dtend = format_ical_date(end_time)
    dtstamp = format_ical_date(datetime.now())

    # Clean description text (remove newlines and escape special chars)
    description = event.description or "No description available"
    # Replace newlines with literal \n and escape commas, semicolons
    description = description.replace('\n', '\\n').replace('\r', '')
    description = description.replace(',', '\\,').replace(';', '\\;')

    # Clean title (escape special chars)
    title = event.title.replace(',', '\\,').replace(';', '\\;')

    # Build location string
    location_parts = []
    if event.venue_name:
        location_parts.append(event.venue_name)
    if event.address:
        location_parts.append(event.address)
    location = ', '.join(location_parts) if location_parts else 'Location TBA'
    location = location.replace(',', '\\,').replace(';', '\\;')

    # Build the .ics content
    ics_lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Westside LA Events//NONSGML Event//EN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{event.id}@westsidelaevents.com',
        f'DTSTAMP:{dtstamp}',
        f'DTSTART:{dtstart}',
        f'DTEND:{dtend}',
        f'SUMMARY:{title}',
        f'DESCRIPTION:{description}',
        f'LOCATION:{location}',
    ]

    # Add URL if available
    if event.url:
        ics_lines.append(f'URL:{event.url}')

    # Add category
    if event.category:
        ics_lines.append(f'CATEGORIES:{event.category}')

    # Add geographic coordinates if available
    if event.latitude and event.longitude:
        ics_lines.append(f'GEO:{event.latitude};{event.longitude}')

    # Close the event and calendar
    ics_lines.extend([
        'STATUS:CONFIRMED',
        'SEQUENCE:0',
        'END:VEVENT',
        'END:VCALENDAR'
    ])

    # Join with CRLF (as per RFC 5545)
    return '\r\n'.join(ics_lines)


def get_ics_filename(event: Event) -> str:
    """
    Generate a safe filename for the .ics file based on event title and date.

    Args:
        event: Event object

    Returns:
        String containing a safe filename (e.g., "event-title-2024-01-15.ics")
    """
    import re

    # Clean the title for use in filename
    # Remove special characters and replace spaces with hyphens
    clean_title = re.sub(r'[^\w\s-]', '', event.title)
    clean_title = re.sub(r'[-\s]+', '-', clean_title)
    clean_title = clean_title.strip('-').lower()

    # Limit length to avoid filesystem issues
    clean_title = clean_title[:50]

    # Format date
    date_str = event.event_date.strftime('%Y-%m-%d')

    return f'{clean_title}-{date_str}.ics'
