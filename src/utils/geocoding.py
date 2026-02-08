"""
Geocoding utility for converting addresses to lat/lng coordinates.
Uses Nominatim (OpenStreetMap) geocoding service - completely free, no API key required.
"""
import json
import time
from pathlib import Path
from typing import Optional, Tuple
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

import config


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

        # Check cache first
        cache_key = address.lower().strip()
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if cached is None:
                return None
            return (cached['lat'], cached['lng'])

        # Try geocoding with retries (Nominatim has rate limit of 1 req/sec)
        for attempt in range(retry):
            try:
                # Respect Nominatim's rate limit (1 request per second)
                time.sleep(1)

                location = self.geolocator.geocode(
                    address,
                    timeout=config.SCRAPER_CONFIG['timeout_seconds']
                )

                if location:
                    result = (location.latitude, location.longitude)
                    # Cache successful result (deferred save)
                    self.cache[cache_key] = {
                        'lat': location.latitude,
                        'lng': location.longitude
                    }
                    self._dirty = True
                    return result
                else:
                    # Cache negative result to avoid repeated lookups
                    self.cache[cache_key] = None
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
        if self._dirty:
            self._save_cache()
            self._dirty = False

    def clear_cache(self):
        """Clear the geocoding cache."""
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


def get_geocoding_service() -> GeocodingService:
    """Get or create the global geocoding service instance."""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service
