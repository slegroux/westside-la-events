"""
Geocoding utility for converting addresses to lat/lng coordinates.
Uses Nominatim (OpenStreetMap) geocoding service - completely free, no API key required.
"""
import json
import re
import threading
import time
from pathlib import Path
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

import config


POSITIVE_TTL_SECONDS = 90 * 86400  # 90 days — addresses occasionally move/re-key
NEGATIVE_TTL_SECONDS = 7 * 86400   # 7 days — transient outages shouldn't poison forever
_CACHE_MISS = object()  # sentinel distinguishing "no entry" from cached-negative None


# Written-out ordinal street names -> numeric form, which Nominatim matches.
_ORDINAL_WORDS = {
    'first': '1st', 'second': '2nd', 'third': '3rd', 'fourth': '4th',
    'fifth': '5th', 'sixth': '6th', 'seventh': '7th', 'eighth': '8th',
    'ninth': '9th', 'tenth': '10th', 'eleventh': '11th', 'twelfth': '12th',
}
_STREET_TYPES = r'st|street|ave|avenue|blvd|boulevard|dr|drive|pl|place|ct|court|rd|road|way|ln|lane'
# Coverage-area cities used as a locality hint when geocoding by venue name.
_CITY_HINTS = (
    'Santa Monica', 'Venice', 'Culver City', 'Marina del Rey', 'Pacific Palisades',
    'Malibu', 'Beverly Hills', 'West Los Angeles', 'Westwood', 'Mar Vista',
    'Playa Vista', 'Playa del Rey', 'Brentwood', 'Inglewood', 'El Segundo',
)


def normalize_address(address: str) -> str:
    """Best-effort cleanup of a messy address into a form Nominatim can match.

    Conservative transforms only: strip parentheticals and any narrative after a
    ZIP, drop suite/unit numbers, collapse a leading street-number range to its
    start, and convert written-out ordinal street names to digits. Returns the
    cleaned address (which may equal the input).
    """
    if not address:
        return ''
    s = address.strip()
    s = re.sub(r'\s*\([^)]*\)', '', s)                       # "(between 4th & Ocean)"
    s = re.sub(r'(\b\d{5}\b).*$', r'\1', s)                  # narrative after a ZIP
    s = re.sub(r'^(\s*\d+)\s*[-–]\s*\d+', r'\1', s)     # "155-199 Foo" -> "155 Foo"
    s = re.sub(r'\s*#\s*\w+', '', s)                         # "#374"
    s = re.sub(r'\s*\b(?:suite|ste|unit|apt|apartment|fl|floor)\b\.?\s*#?\s*\w+', '', s, flags=re.I)
    s = re.sub(
        r'\b(' + '|'.join(_ORDINAL_WORDS) + r')\b(?=\s+(?:' + _STREET_TYPES + r')\b)',
        lambda m: _ORDINAL_WORDS[m.group(1).lower()],
        s, flags=re.I,
    )
    s = re.sub(r'\s{2,}', ' ', s).strip().strip(',').strip()
    return s


def _extract_city_hint(address: str) -> str:
    """Pick a 'City, CA' locality from an address, for venue-name fallback."""
    if address:
        low = address.lower()
        for city in _CITY_HINTS:
            if city.lower() in low:
                return f'{city}, CA'
    return 'Los Angeles, CA'


class GeocodingService:
    """Service for geocoding addresses with caching."""

    def __init__(self, api_key: Optional[str] = None, cache_file: Optional[str] = None):
        """
        Initialize geocoding service.

        Args:
            api_key: Not used (kept for backwards compatibility)
            cache_file: Path to cache file for storing geocoding results
        """
        self.cache_file = cache_file or config.GEOCODE_CACHE_FILE
        # Use Nominatim with a user agent (required by OpenStreetMap's usage policy)
        self.geolocator = Nominatim(user_agent="westside_la_events/1.0")
        self.cache = self._load_cache()
        self._dirty = False
        # The geocoding service is shared across the scraper thread pool, so
        # cache mutations and the _dirty flag need locking. RLock so that
        # flush/clear can be called from inside a locked region if needed.
        self._lock = threading.RLock()

    def _load_cache(self) -> dict:
        """Load geocoding cache from file."""
        cache_path = Path(self.cache_file)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        """Save geocoding cache to file."""
        cache_path = Path(self.cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cache_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save geocoding cache: {e}")

    def _lookup_cached(self, cache_key: str, now: float):
        """
        Look up a cache entry under lock. Returns:
          - (lat, lng) tuple for a fresh positive hit
          - None for a fresh negative hit (cached miss)
          - _CACHE_MISS sentinel if absent or expired

        Lazily migrates legacy positive entries to the timestamped schema
        and evicts expired entries.
        """
        if cache_key not in self.cache:
            return _CACHE_MISS
        cached = self.cache[cache_key]

        # Legacy bare-None negative — treat as expired and re-geocode
        if cached is None or not isinstance(cached, dict):
            del self.cache[cache_key]
            self._dirty = True
            return _CACHE_MISS

        # Legacy positive: {'lat': ..., 'lng': ...} — migrate, return
        if 'lat' in cached and 'lng' in cached:
            coords = (cached['lat'], cached['lng'])
            self.cache[cache_key] = {
                'result': {'lat': coords[0], 'lng': coords[1]},
                'cached_at': now,
            }
            self._dirty = True
            return coords

        result = cached.get('result')
        cached_at = cached.get('cached_at', 0)

        if result is None:
            if now - cached_at < NEGATIVE_TTL_SECONDS:
                return None
            del self.cache[cache_key]
            self._dirty = True
            return _CACHE_MISS

        # Positive entry — apply TTL, lazy-stamp legacy entries missing cached_at
        if cached_at == 0:
            cached['cached_at'] = now
            self._dirty = True
            return (result['lat'], result['lng'])
        if now - cached_at < POSITIVE_TTL_SECONDS:
            return (result['lat'], result['lng'])
        del self.cache[cache_key]
        self._dirty = True
        return _CACHE_MISS

    def geocode(self, address: str, retry: int = 3) -> Optional[Tuple[float, float]]:
        """
        Geocode an address to latitude and longitude.

        Args:
            address: Address string to geocode
            retry: Number of retries on failure

        Returns:
            Tuple of (latitude, longitude) or None if geocoding fails
        """
        if not address or not address.strip():
            return None

        cache_key = address.lower().strip()
        now = time.time()

        with self._lock:
            cached = self._lookup_cached(cache_key, now)
        if cached is not _CACHE_MISS:
            return cached  # coords tuple or None for cached-negative

        # Cache miss — geocode. Do the network call outside the lock so
        # other threads can read/write the cache concurrently.
        for attempt in range(retry):
            try:
                # Respect Nominatim's rate limit (1 request per second)
                time.sleep(1)

                location = self.geolocator.geocode(
                    address,
                    timeout=config.SCRAPER_CONFIG['timeout_seconds']
                )

                if location:
                    coords = (location.latitude, location.longitude)
                    with self._lock:
                        self.cache[cache_key] = {
                            'result': {'lat': coords[0], 'lng': coords[1]},
                            'cached_at': time.time(),
                        }
                        self._dirty = True
                    return coords

                with self._lock:
                    self.cache[cache_key] = {'result': None, 'cached_at': time.time()}
                    self._dirty = True
                return None

            except GeocoderTimedOut:
                if attempt < retry - 1:
                    time.sleep(2)
                    continue
                print(f"Geocoding timeout for address: {address}")
                return None

            except GeocoderServiceError as e:
                print(f"Geocoding service error for address '{address}': {e}")
                return None

            except Exception as e:
                print(f"Unexpected geocoding error for address '{address}': {e}")
                return None

        return None

    def geocode_with_fallback(
        self, address: str, venue_name: Optional[str] = None
    ) -> Optional[Tuple[float, float]]:
        """Geocode an address, retrying with a normalized form and finally a
        venue-name + city lookup before giving up.

        Many scraped addresses fail Nominatim verbatim (street-number ranges,
        "#" suites, parentheticals, written-out ordinals, trailing narrative).
        This tries progressively cleaner queries so the event still lands on the
        map instead of silently dropping off it.
        """
        if address and address.strip():
            coords = self.geocode(address)
            if coords:
                return coords
            normalized = normalize_address(address)
            if normalized and normalized.lower() != address.lower().strip():
                coords = self.geocode(normalized)
                if coords:
                    return coords

        if venue_name and venue_name.strip():
            coords = self.geocode(f'{venue_name.strip()}, {_extract_city_hint(address)}')
            if coords:
                return coords

        return None

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[str]:
        """
        Reverse geocode coordinates to an address.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Address string or None if reverse geocoding fails
        """
        if not self.geolocator:
            return None

        try:
            location = self.geolocator.reverse(
                (latitude, longitude),
                timeout=config.SCRAPER_CONFIG['timeout_seconds']
            )
            return location.address if location else None

        except Exception as e:
            print(f"Reverse geocoding error for ({latitude}, {longitude}): {e}")
            return None

    def flush_cache(self):
        """Save geocoding cache to disk if there are unsaved changes."""
        with self._lock:
            if self._dirty:
                self._save_cache()
                self._dirty = False

    def clear_cache(self):
        """Clear the geocoding cache."""
        with self._lock:
            self.cache = {}
            self._save_cache()
            self._dirty = False

    def is_in_westside(self, latitude: float, longitude: float) -> bool:
        """
        Check if coordinates are within Westside LA bounds.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            True if coordinates are in Westside LA, False otherwise
        """
        bounds = config.WESTSIDE_BOUNDS
        return (
            bounds['min_lat'] <= latitude <= bounds['max_lat'] and
            bounds['min_lng'] <= longitude <= bounds['max_lng']
        )


# Global geocoding service instance
_geocoding_service = None
_geocoding_service_lock = threading.Lock()


def get_geocoding_service() -> GeocodingService:
    """Get or create the global geocoding service instance."""
    global _geocoding_service
    if _geocoding_service is not None:
        return _geocoding_service
    with _geocoding_service_lock:
        # Double-checked: another thread may have initialized while we waited.
        if _geocoding_service is None:
            _geocoding_service = GeocodingService()
    return _geocoding_service
