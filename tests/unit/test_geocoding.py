"""
Unit tests for the geocoding utility (src/utils/geocoding.py).

The module hits the Nominatim (OpenStreetMap) network service and persists a
JSON cache to disk. These tests NEVER touch the real network or the real
``data/geocode_cache.json`` file:

  - Every ``GeocodingService`` is constructed with a ``tmp_path``-based cache
    file, so the production cache is never read or written.
  - The underlying ``geolocator`` (the only object that performs network I/O)
    is replaced with a fake before any geocode call is made.
  - ``time.sleep`` is patched out so the rate-limit / retry sleeps don't slow
    the suite down.

The module-level singleton (``_geocoding_service``) is reset around tests that
exercise ``get_geocoding_service()``.
"""
import os

import pytest

import config
from src.utils import geocoding
from src.utils.geocoding import (
    GeocodingService,
    POSITIVE_TTL_SECONDS,
    NEGATIVE_TTL_SECONDS,
    _CACHE_MISS,
    get_geocoding_service,
)
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


# ---------------------------------------------------------------------------
# Test doubles / helpers
# ---------------------------------------------------------------------------

class _FakeLocation:
    """Stand-in for a geopy Location object (only the attributes used)."""

    def __init__(self, latitude, longitude, address="123 Fake St"):
        self.latitude = latitude
        self.longitude = longitude
        self.address = address


class _FakeGeolocator:
    """
    Replaces ``GeocodingService.geolocator`` so no network call ever happens.

    ``geocode_result``/``geocode_exc`` control what ``geocode`` does; same for
    reverse. ``calls`` records how many times ``geocode`` was invoked so tests
    can assert the network was (not) hit.
    """

    def __init__(self, geocode_result=None, geocode_exc=None,
                 reverse_result=None, reverse_exc=None):
        self.geocode_result = geocode_result
        self.geocode_exc = geocode_exc
        self.reverse_result = reverse_result
        self.reverse_exc = reverse_exc
        self.calls = 0
        self.reverse_calls = 0

    def geocode(self, address, timeout=None):
        self.calls += 1
        if self.geocode_exc is not None:
            raise self.geocode_exc
        return self.geocode_result

    def reverse(self, coords, timeout=None):
        self.reverse_calls += 1
        if self.reverse_exc is not None:
            raise self.reverse_exc
        return self.reverse_result


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Neutralize the rate-limit/retry sleeps so tests run instantly."""
    monkeypatch.setattr(geocoding.time, "sleep", lambda *a, **k: None)


@pytest.fixture
def service_factory(tmp_path):
    """
    Factory that builds a GeocodingService backed by a tmp_path cache file and
    a fake geolocator. Returns (service, fake_geolocator).
    """
    def _make(fake=None, cache_name="geocode_cache.json"):
        cache_file = str(tmp_path / cache_name)
        svc = GeocodingService(cache_file=cache_file)
        fake = fake or _FakeGeolocator()
        svc.geolocator = fake
        return svc, fake

    return _make


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure the module-level singleton never leaks between tests."""
    geocoding._geocoding_service = None
    yield
    geocoding._geocoding_service = None


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestInitialization:
    """Construction and cache loading."""

    def test_uses_provided_cache_file(self, tmp_path):
        cache_file = str(tmp_path / "my_cache.json")
        svc = GeocodingService(cache_file=cache_file)
        assert svc.cache_file == cache_file
        # Fresh (nonexistent) cache file -> empty dict
        assert svc.cache == {}
        assert svc._dirty is False

    def test_defaults_to_config_cache_file(self, monkeypatch):
        # Don't actually load the real file; just confirm the default wiring.
        monkeypatch.setattr(GeocodingService, "_load_cache", lambda self: {})
        svc = GeocodingService()
        assert svc.cache_file == config.GEOCODE_CACHE_FILE

    def test_load_cache_reads_existing_json(self, tmp_path):
        import json
        cache_file = tmp_path / "preexisting.json"
        cache_file.write_text(json.dumps({
            "123 main st": {"result": {"lat": 1.0, "lng": 2.0}, "cached_at": 0}
        }))
        svc = GeocodingService(cache_file=str(cache_file))
        assert "123 main st" in svc.cache

    def test_load_cache_handles_corrupt_json(self, tmp_path):
        cache_file = tmp_path / "corrupt.json"
        cache_file.write_text("{not valid json")
        svc = GeocodingService(cache_file=str(cache_file))
        # Corrupt file -> empty cache, not a crash
        assert svc.cache == {}


# ---------------------------------------------------------------------------
# Cache hit behavior (no network)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCacheHit:
    """A fresh cached entry must short-circuit the network entirely."""

    def test_positive_cache_hit_returns_coords_without_network(self, service_factory):
        svc, fake = service_factory()
        # Pre-seed a fresh positive entry using the timestamped schema.
        import time as _time
        svc.cache["123 ocean ave"] = {
            "result": {"lat": 34.01, "lng": -118.49},
            "cached_at": _time.time(),
        }
        result = svc.geocode("123 Ocean Ave")
        assert result == (34.01, -118.49)
        # Crucially: the network geocoder was never called.
        assert fake.calls == 0

    def test_negative_cache_hit_returns_none_without_network(self, service_factory):
        svc, fake = service_factory()
        import time as _time
        svc.cache["nowhere"] = {"result": None, "cached_at": _time.time()}
        result = svc.geocode("Nowhere")
        assert result is None
        assert fake.calls == 0

    def test_cache_key_is_normalized(self, service_factory):
        """Lookups are case-insensitive and whitespace-trimmed."""
        svc, fake = service_factory()
        import time as _time
        svc.cache["123 ocean ave"] = {
            "result": {"lat": 1.0, "lng": 2.0},
            "cached_at": _time.time(),
        }
        # Mixed case + surrounding whitespace must hit the same key.
        assert svc.geocode("  123 OCEAN Ave  ") == (1.0, 2.0)
        assert fake.calls == 0

    def test_empty_address_returns_none_without_network(self, service_factory):
        svc, fake = service_factory()
        assert svc.geocode("") is None
        assert svc.geocode("   ") is None
        assert fake.calls == 0


# ---------------------------------------------------------------------------
# _lookup_cached TTL logic
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLookupCachedTTL:
    """Directly exercise positive/negative TTL behavior of _lookup_cached."""

    def test_missing_key_returns_cache_miss(self, service_factory):
        svc, _ = service_factory()
        assert svc._lookup_cached("absent", now=1000.0) is _CACHE_MISS

    def test_fresh_positive_within_ttl(self, service_factory):
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {"result": {"lat": 10.0, "lng": 20.0}, "cached_at": now - 1}
        assert svc._lookup_cached("k", now) == (10.0, 20.0)

    def test_positive_just_inside_ttl(self, service_factory):
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {
            "result": {"lat": 10.0, "lng": 20.0},
            "cached_at": now - (POSITIVE_TTL_SECONDS - 1),
        }
        assert svc._lookup_cached("k", now) == (10.0, 20.0)

    def test_expired_positive_evicted_and_misses(self, service_factory):
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {
            "result": {"lat": 10.0, "lng": 20.0},
            "cached_at": now - (POSITIVE_TTL_SECONDS + 1),
        }
        assert svc._lookup_cached("k", now) is _CACHE_MISS
        # Expired positive entry is evicted and cache marked dirty.
        assert "k" not in svc.cache
        assert svc._dirty is True

    def test_fresh_negative_within_ttl_returns_none(self, service_factory):
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {"result": None, "cached_at": now - 1}
        # A fresh negative is a real cached miss -> None (NOT _CACHE_MISS).
        assert svc._lookup_cached("k", now) is None
        # Still present (not evicted) since it's fresh.
        assert "k" in svc.cache

    def test_negative_just_inside_ttl_returns_none(self, service_factory):
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {
            "result": None,
            "cached_at": now - (NEGATIVE_TTL_SECONDS - 1),
        }
        assert svc._lookup_cached("k", now) is None

    def test_expired_negative_evicted_and_misses(self, service_factory):
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {
            "result": None,
            "cached_at": now - (NEGATIVE_TTL_SECONDS + 1),
        }
        assert svc._lookup_cached("k", now) is _CACHE_MISS
        assert "k" not in svc.cache
        assert svc._dirty is True

    def test_negative_ttl_shorter_than_positive_ttl(self):
        """Document the intended relationship between the two TTL constants."""
        assert NEGATIVE_TTL_SECONDS < POSITIVE_TTL_SECONDS

    def test_legacy_bare_none_treated_as_expired(self, service_factory):
        svc, _ = service_factory()
        svc.cache["k"] = None
        assert svc._lookup_cached("k", now=1000.0) is _CACHE_MISS
        assert "k" not in svc.cache
        assert svc._dirty is True

    def test_legacy_positive_schema_migrated(self, service_factory):
        """Legacy {'lat','lng'} entries are returned and migrated in place."""
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {"lat": 5.0, "lng": 6.0}
        assert svc._lookup_cached("k", now) == (5.0, 6.0)
        migrated = svc.cache["k"]
        assert migrated["result"] == {"lat": 5.0, "lng": 6.0}
        assert migrated["cached_at"] == now
        assert svc._dirty is True

    def test_legacy_positive_missing_timestamp_is_stamped(self, service_factory):
        """Positive entry with cached_at==0 is lazily stamped, not evicted."""
        svc, _ = service_factory()
        now = 1_000_000.0
        svc.cache["k"] = {"result": {"lat": 7.0, "lng": 8.0}, "cached_at": 0}
        assert svc._lookup_cached("k", now) == (7.0, 8.0)
        assert svc.cache["k"]["cached_at"] == now
        assert svc._dirty is True


# ---------------------------------------------------------------------------
# Network success path (cache miss -> geocode)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGeocodeNetwork:
    """Cache-miss path that calls the (faked) geolocator."""

    def test_successful_geocode_caches_positive(self, service_factory):
        fake = _FakeGeolocator(geocode_result=_FakeLocation(34.05, -118.24))
        svc, fake = service_factory(fake=fake)
        result = svc.geocode("Some Address")
        assert result == (34.05, -118.24)
        assert fake.calls == 1
        # Positive result is cached under the normalized key.
        cached = svc.cache["some address"]
        assert cached["result"] == {"lat": 34.05, "lng": -118.24}
        assert "cached_at" in cached
        assert svc._dirty is True

    def test_second_call_uses_cache_not_network(self, service_factory):
        fake = _FakeGeolocator(geocode_result=_FakeLocation(1.0, 2.0))
        svc, fake = service_factory(fake=fake)
        assert svc.geocode("Repeat Me") == (1.0, 2.0)
        # Second call must be served from cache; no extra network call.
        assert svc.geocode("Repeat Me") == (1.0, 2.0)
        assert fake.calls == 1

    def test_no_location_caches_negative(self, service_factory):
        # geolocator returns None (address not found)
        fake = _FakeGeolocator(geocode_result=None)
        svc, fake = service_factory(fake=fake)
        assert svc.geocode("Unfindable") is None
        assert fake.calls == 1
        # Negative result cached so we don't re-hit the network.
        assert svc.cache["unfindable"]["result"] is None
        assert svc._dirty is True
        # Subsequent call served from negative cache.
        assert svc.geocode("Unfindable") is None
        assert fake.calls == 1


# ---------------------------------------------------------------------------
# Graceful error handling
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGeocodeErrorHandling:
    """Geocoder exceptions must yield None, never propagate."""

    def test_timeout_exhausts_retries_returns_none(self, service_factory):
        fake = _FakeGeolocator(geocode_exc=GeocoderTimedOut("timed out"))
        svc, fake = service_factory(fake=fake)
        result = svc.geocode("Times Out", retry=3)
        assert result is None
        # All 3 attempts were made before giving up.
        assert fake.calls == 3
        # NOTE: a persistent timeout returns None but does NOT write a negative
        # cache entry (the except branch returns directly). Document actual
        # behavior: the key is absent so the next call retries the network.
        assert "times out" not in svc.cache

    def test_service_error_returns_none_immediately(self, service_factory):
        fake = _FakeGeolocator(geocode_exc=GeocoderServiceError("503"))
        svc, fake = service_factory(fake=fake)
        result = svc.geocode("Service Error", retry=3)
        assert result is None
        # Service errors do not retry — single attempt.
        assert fake.calls == 1
        assert "service error" not in svc.cache

    def test_unexpected_exception_returns_none(self, service_factory):
        fake = _FakeGeolocator(geocode_exc=ValueError("boom"))
        svc, fake = service_factory(fake=fake)
        result = svc.geocode("Kaboom", retry=3)
        assert result is None
        assert fake.calls == 1
        assert "kaboom" not in svc.cache


# ---------------------------------------------------------------------------
# Reverse geocoding
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReverseGeocode:
    def test_reverse_returns_address(self, service_factory):
        fake = _FakeGeolocator(reverse_result=_FakeLocation(0, 0, address="1 Infinite Loop"))
        svc, fake = service_factory(fake=fake)
        assert svc.reverse_geocode(34.0, -118.0) == "1 Infinite Loop"
        assert fake.reverse_calls == 1

    def test_reverse_no_result_returns_none(self, service_factory):
        fake = _FakeGeolocator(reverse_result=None)
        svc, fake = service_factory(fake=fake)
        assert svc.reverse_geocode(34.0, -118.0) is None

    def test_reverse_exception_returns_none(self, service_factory):
        fake = _FakeGeolocator(reverse_exc=GeocoderServiceError("nope"))
        svc, fake = service_factory(fake=fake)
        assert svc.reverse_geocode(34.0, -118.0) is None

    def test_reverse_no_geolocator_returns_none(self, service_factory):
        svc, _ = service_factory()
        svc.geolocator = None
        assert svc.reverse_geocode(34.0, -118.0) is None


# ---------------------------------------------------------------------------
# Cache persistence: flush / clear
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCachePersistence:
    def test_flush_writes_dirty_cache_to_disk(self, service_factory, tmp_path):
        import json
        svc, _ = service_factory()
        svc.cache["addr"] = {"result": {"lat": 1.0, "lng": 2.0}, "cached_at": 0}
        svc._dirty = True
        svc.flush_cache()
        assert svc._dirty is False
        on_disk = json.loads(open(svc.cache_file).read())
        assert on_disk["addr"]["result"] == {"lat": 1.0, "lng": 2.0}

    def test_flush_noop_when_not_dirty(self, service_factory):
        svc, _ = service_factory()
        # Not dirty -> no file written.
        assert svc._dirty is False
        svc.flush_cache()
        assert not os.path.exists(svc.cache_file)

    def test_clear_cache_empties_and_persists(self, service_factory):
        import json
        svc, _ = service_factory()
        svc.cache["addr"] = {"result": {"lat": 1.0, "lng": 2.0}, "cached_at": 0}
        svc._dirty = True
        svc.clear_cache()
        assert svc.cache == {}
        assert svc._dirty is False
        # clear_cache always saves -> file on disk is an empty object.
        on_disk = json.loads(open(svc.cache_file).read())
        assert on_disk == {}


# ---------------------------------------------------------------------------
# is_in_westside delegation to config.WESTSIDE_BOUNDS
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestIsInWestside:
    def test_point_inside_bounds(self, service_factory):
        svc, _ = service_factory()
        b = config.WESTSIDE_BOUNDS
        lat = (b["min_lat"] + b["max_lat"]) / 2
        lng = (b["min_lng"] + b["max_lng"]) / 2
        assert svc.is_in_westside(lat, lng) is True

    def test_point_outside_bounds_north(self, service_factory):
        svc, _ = service_factory()
        b = config.WESTSIDE_BOUNDS
        assert svc.is_in_westside(b["max_lat"] + 1.0, b["min_lng"]) is False

    def test_point_outside_bounds_east(self, service_factory):
        svc, _ = service_factory()
        b = config.WESTSIDE_BOUNDS
        # Downtown LA is east of the east boundary -> excluded.
        assert svc.is_in_westside(34.05, -118.24) is False

    def test_boundary_edges_inclusive(self, service_factory):
        svc, _ = service_factory()
        b = config.WESTSIDE_BOUNDS
        # Bounds checks use <= on every edge, so corners are inclusive.
        assert svc.is_in_westside(b["min_lat"], b["min_lng"]) is True
        assert svc.is_in_westside(b["max_lat"], b["max_lng"]) is True


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestGetGeocodingService:
    def test_returns_singleton_instance(self, monkeypatch):
        # Avoid loading the real cache file from disk.
        monkeypatch.setattr(GeocodingService, "_load_cache", lambda self: {})
        a = get_geocoding_service()
        b = get_geocoding_service()
        assert a is b
        assert isinstance(a, GeocodingService)
