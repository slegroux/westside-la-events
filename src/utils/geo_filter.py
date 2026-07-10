"""Geographic filtering utilities for LA Westside and Malibu events."""

from math import radians, sin, cos, sqrt, atan2
from typing import Tuple, Optional
import re


# Westside LA + Malibu approximate boundaries
# Includes: Santa Monica, Venice, Westwood, Brentwood, Pacific Palisades,
#           West LA, Culver City, Inglewood (SoFi Stadium, Intuit Dome, Kia Forum)
WESTSIDE_BOUNDS = {
    'north': 34.0900,  # Sunset Blvd area (Westside proper)
    'south': 33.9400,  # Inglewood area (includes SoFi Stadium, Intuit Dome)
    # ~La Brea Ave. Matches config.WESTSIDE_BOUNDS max_lng (the documented
    # eastern edge). Keeps Culver City (~-118.39) and Inglewood/SoFi (~-118.34)
    # while excluding Hollywood, Hancock Park/Larchmont (~-118.32) and points
    # further east. NOTE: -118.2500 previously let in Hollywood/Mid-Wilshire.
    'east': -118.3300,
    'west': -118.5500   # Pacific Ocean
}

MALIBU_BOUNDS = {
    'north': 34.0800,  # Malibu hills
    'south': 34.0000,  # Malibu coast
    'east': -118.5500,  # Eastern Malibu (borders Westside)
    'west': -118.9500   # Western Malibu (Ventura County line)
}

# Westside neighborhoods (case-insensitive matching)
WESTSIDE_NEIGHBORHOODS = {
    'santa monica', 'venice', 'marina del rey', 'playa vista',
    'playa del rey', 'westchester', 'brentwood', 'west la',
    'west los angeles', 'palms', 'mar vista', 'culver city',
    'westwood', 'sawtelle', 'pacific palisades', 'beverly hills',
    'century city', 'inglewood', 'el segundo',
    'malibu', 'topanga', 'topanga beach', 'el matador', 'zuma beach',
    'point dume', 'carbon beach', 'surfrider beach',
    'ucla', 'ucla campus'  # UCLA campus is in Westwood
}

# Zip codes for Westside and Malibu
WESTSIDE_ZIP_CODES = {
    # Santa Monica
    '90401', '90402', '90403', '90404', '90405',
    # Venice
    '90291', '90292',
    # Playa Del Rey / Marina Del Rey
    '90293', '90294',
    # Mar Vista / Palms
    '90066', '90034',
    # West LA / Westwood / Sawtelle
    '90025', '90064', '90024',
    # Brentwood / Pacific Palisades
    '90049',
    # Westchester
    '90045',
    # El Segundo
    '90245',
    # Culver City
    '90230', '90232',
    # Inglewood
    '90301', '90302', '90303', '90304', '90305',
    # Century City area
    '90067', '90035',
    # Beverly Hills
    '90210', '90211', '90212',
    # Malibu
    '90263', '90264', '90265'
}

# Specific non-Westside venues to always exclude, even when their coordinates
# fall inside the coverage bounding box. These are aggregator-listed (e.g. Shore
# Hotel) farmers markets in Mid-City / Beverly Grove / Miracle Mile that share
# coordinates and zip codes with legitimate venues nearby (LACMA, the Academy
# Museum, the Petersen, etc.), so they cannot be excluded geographically.
# Matched as case-insensitive substrings against the venue name and title.
NON_WESTSIDE_VENUE_DENYLIST = (
    'miracle mile certified farmers market',
    'melrose place certified farmers market',
    'la cienega farmers market',
    'farm habit certified farmers market',     # at Cedars-Sinai (Beverly Grove)
    'wellington square certified farmers',
)

# Specific venues outside the Westside box that are explicitly included anyway,
# by the site owner's choice (mirrors the Inglewood inclusion). Events whose
# venue/title matches one of these bypass the coverage-area filter entirely.
WESTSIDE_VENUE_ALLOWLIST = (
    'io music academy',     # Hollywood DJ/production academy (ra.co/clubs/282834)
)

# Reference point: Santa Monica Pier
SANTA_MONICA_PIER = (34.0095, -118.4977)
MAX_DISTANCE_MILES = 12  # Radius to consider "Westside" (covers Malibu, excludes Hollywood/DTLA)


def is_in_westside(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are within Westside LA boundaries.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        True if coordinates are within Westside bounds
    """
    return (
        WESTSIDE_BOUNDS['south'] <= latitude <= WESTSIDE_BOUNDS['north'] and
        WESTSIDE_BOUNDS['west'] <= longitude <= WESTSIDE_BOUNDS['east']
    )


def is_in_malibu(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are within Malibu boundaries.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        True if coordinates are within Malibu bounds
    """
    return (
        MALIBU_BOUNDS['south'] <= latitude <= MALIBU_BOUNDS['north'] and
        MALIBU_BOUNDS['west'] <= longitude <= MALIBU_BOUNDS['east']
    )


def is_in_coverage_area(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are within our coverage area (Westside OR Malibu).

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        True if coordinates are within coverage area
    """
    return is_in_westside(latitude, longitude) or is_in_malibu(latitude, longitude)


def haversine_distance(lat1: float, lon1: float,
                       lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in miles using Haversine formula.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in miles
    """
    R = 3959  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def is_within_coverage_radius(latitude: float, longitude: float,
                               max_miles: float = MAX_DISTANCE_MILES) -> bool:
    """
    Check if coordinates are within radius of Westside reference point.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        max_miles: Maximum distance in miles (default: 15)

    Returns:
        True if coordinates are within radius
    """
    distance = haversine_distance(
        latitude, longitude,
        SANTA_MONICA_PIER[0], SANTA_MONICA_PIER[1]
    )
    return distance <= max_miles


def extract_zip_codes(text: str) -> list[str]:
    """
    Extract US zip codes from text.

    Args:
        text: Text to search for zip codes

    Returns:
        List of 5-digit zip codes found
    """
    if not text:
        return []
    return re.findall(r'\b\d{5}\b', text)


def is_westside_address(address: str, city: str = None, venue_name: str = None) -> bool:
    """
    Check if address/venue is in Westside/Malibu based on text matching.

    Args:
        address: Street address
        city: City name (optional)
        venue_name: Venue name (optional)

    Returns:
        True if address appears to be in coverage area
    """
    # Combine all text for searching
    search_text = ' '.join(filter(None, [address or '', city or '', venue_name or ''])).lower()

    if not search_text:
        return False

    # Check for city names
    if city:
        city_lower = city.lower()
        if city_lower in {'santa monica', 'venice', 'culver city',
                          'beverly hills', 'west hollywood', 'inglewood', 'el segundo', 'malibu'}:
            return True

    # Check for neighborhoods in any text
    for neighborhood in WESTSIDE_NEIGHBORHOODS:
        if neighborhood in search_text:
            return True

    # Check zip codes
    zip_codes = extract_zip_codes(search_text)
    if any(zip_code in WESTSIDE_ZIP_CODES for zip_code in zip_codes):
        return True

    return False


def is_denylisted_venue(venue_name: Optional[str] = None,
                        title: Optional[str] = None) -> bool:
    """Return True if the venue/title matches a known non-Westside venue.

    Used to exclude specific aggregator-listed venues (e.g. Mid-City farmers
    markets) that fall inside the coverage box but are not part of the Westside
    and cannot be separated geographically from nearby legitimate venues.
    """
    haystack = ' '.join(filter(None, [venue_name or '', title or ''])).lower()
    if not haystack:
        return False
    return any(term in haystack for term in NON_WESTSIDE_VENUE_DENYLIST)


def is_allowlisted_venue(venue_name: Optional[str] = None,
                         title: Optional[str] = None) -> bool:
    """Return True if the venue/title is an explicitly-included out-of-area venue.

    These bypass the Westside coverage-area filter (see WESTSIDE_VENUE_ALLOWLIST).
    """
    haystack = ' '.join(filter(None, [venue_name or '', title or ''])).lower()
    if not haystack:
        return False
    return any(term in haystack for term in WESTSIDE_VENUE_ALLOWLIST)


def validate_event_location(latitude: Optional[float] = None,
                            longitude: Optional[float] = None,
                            address: Optional[str] = None,
                            city: Optional[str] = None,
                            venue_name: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate if event is in coverage area using all available information.

    Prioritizes coordinate-based validation when available, falls back to text matching.

    Args:
        latitude: Latitude coordinate (optional)
        longitude: Longitude coordinate (optional)
        address: Street address (optional)
        city: City name (optional)
        venue_name: Venue name (optional)

    Returns:
        Tuple of (is_valid, reason)
    """
    # Method 1: Check coordinates if available (most accurate)
    if latitude is not None and longitude is not None:
        # First check bounding boxes (strict geographic boundaries)
        if is_in_coverage_area(latitude, longitude):
            return True, "coordinates_in_bounds"

        # For edge cases, check if address text suggests it should be included
        # (e.g., Malibu locations slightly outside the box)
        if address or city or venue_name:
            if is_westside_address(address, city, venue_name):
                # Even if coords are slightly off, trust the address
                if is_within_coverage_radius(latitude, longitude):
                    return True, "address_match_near_area"

        # Definitely outside coverage area
        return False, "coordinates_outside_area"

    # Method 2: Check address/city/venue text when no coordinates
    if address or city or venue_name:
        if is_westside_address(address, city, venue_name):
            return True, "address_text_match"
        return False, "address_not_recognized"

    # No location information available
    return False, "no_location_info"


def get_location_area(latitude: float, longitude: float) -> str:
    """
    Determine which area (Westside or Malibu) the coordinates are in.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        'westside', 'malibu', or 'outside'
    """
    if is_in_westside(latitude, longitude):
        return 'westside'
    elif is_in_malibu(latitude, longitude):
        return 'malibu'
    else:
        return 'outside'


if __name__ == '__main__':
    # Test examples
    test_locations = [
        ("Santa Monica Pier", 34.0095, -118.4977),
        ("Malibu Beach", 34.0259, -118.7798),
        ("Venice Beach", 33.9850, -118.4695),
        ("Downtown LA (should fail)", 34.0522, -118.2437),
        ("Pasadena (should fail)", 34.1478, -118.1445),
    ]

    print("Testing location validation:")
    print("-" * 70)
    for name, lat, lon in test_locations:
        is_valid, reason = validate_event_location(latitude=lat, longitude=lon)
        area = get_location_area(lat, lon) if is_valid else "N/A"
        status = "✓" if is_valid else "✗"
        print(f"{status} {name:30s} -> {reason:25s} [{area}]")
