"""
Unit tests for the geographic filtering utilities.
"""
import pytest

from src.utils.geo_filter import (
    WESTSIDE_BOUNDS,
    MALIBU_BOUNDS,
    SANTA_MONICA_PIER,
    haversine_distance,
    is_in_westside,
    is_in_malibu,
    is_in_coverage_area,
    is_within_coverage_radius,
    extract_zip_codes,
    is_westside_address,
    validate_event_location,
    get_location_area,
)


# Well-known LA coordinates used across tests
SANTA_MONICA_PIER_COORDS = (34.0095, -118.4977)  # clearly inside Westside
VENICE_BEACH = (33.9850, -118.4695)              # clearly inside Westside
MALIBU_BEACH = (34.0259, -118.7798)              # clearly inside Malibu
DOWNTOWN_LA = (34.0522, -118.2437)               # outside (east of Westside)
PASADENA = (34.1478, -118.1445)                  # outside (north + east)


@pytest.mark.unit
class TestHaversineDistance:
    """Test the haversine_distance helper (returns miles)."""

    def test_zero_distance_same_point(self):
        """Distance from a point to itself is ~0."""
        lat, lon = SANTA_MONICA_PIER_COORDS
        assert haversine_distance(lat, lon, lat, lon) == pytest.approx(0.0, abs=1e-6)

    def test_symmetric(self):
        """Distance is the same regardless of argument order."""
        d1 = haversine_distance(*SANTA_MONICA_PIER_COORDS, *DOWNTOWN_LA)
        d2 = haversine_distance(*DOWNTOWN_LA, *SANTA_MONICA_PIER_COORDS)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_known_distance_smpier_to_dtla(self):
        """Santa Monica Pier -> Downtown LA is roughly 14-16 miles."""
        d = haversine_distance(*SANTA_MONICA_PIER_COORDS, *DOWNTOWN_LA)
        # Great-circle distance between these two points is ~14.5 miles.
        assert 13.0 < d < 17.0

    def test_returns_positive_for_distinct_points(self):
        d = haversine_distance(*SANTA_MONICA_PIER_COORDS, *MALIBU_BEACH)
        assert d > 0


@pytest.mark.unit
class TestIsInWestside:
    """Test the bounding-box check for Westside LA."""

    def test_clearly_inside(self):
        assert is_in_westside(*SANTA_MONICA_PIER_COORDS) is True
        assert is_in_westside(*VENICE_BEACH) is True

    def test_clearly_outside_east(self):
        # Downtown LA longitude is east of the Westside east bound (-118.25).
        assert is_in_westside(*DOWNTOWN_LA) is False

    def test_clearly_outside_north(self):
        # Pasadena is north of the north bound and east of the east bound.
        assert is_in_westside(*PASADENA) is False

    def test_boundary_corners_inclusive(self):
        """Bounds are inclusive on all four edges."""
        assert is_in_westside(WESTSIDE_BOUNDS['south'], WESTSIDE_BOUNDS['west']) is True
        assert is_in_westside(WESTSIDE_BOUNDS['north'], WESTSIDE_BOUNDS['east']) is True
        assert is_in_westside(WESTSIDE_BOUNDS['south'], WESTSIDE_BOUNDS['east']) is True
        assert is_in_westside(WESTSIDE_BOUNDS['north'], WESTSIDE_BOUNDS['west']) is True

    def test_just_outside_bounds(self):
        """A hair beyond each edge falls outside."""
        eps = 0.0001
        assert is_in_westside(WESTSIDE_BOUNDS['north'] + eps, WESTSIDE_BOUNDS['west']) is False
        assert is_in_westside(WESTSIDE_BOUNDS['south'] - eps, WESTSIDE_BOUNDS['west']) is False
        assert is_in_westside(WESTSIDE_BOUNDS['south'], WESTSIDE_BOUNDS['east'] + eps) is False
        assert is_in_westside(WESTSIDE_BOUNDS['south'], WESTSIDE_BOUNDS['west'] - eps) is False


@pytest.mark.unit
class TestIsInMalibu:
    """Test the bounding-box check for Malibu."""

    def test_clearly_inside(self):
        assert is_in_malibu(*MALIBU_BEACH) is True

    def test_clearly_outside(self):
        # Santa Monica Pier longitude is east of the Malibu east bound (-118.55).
        assert is_in_malibu(*SANTA_MONICA_PIER_COORDS) is False
        assert is_in_malibu(*DOWNTOWN_LA) is False

    def test_boundary_corners_inclusive(self):
        assert is_in_malibu(MALIBU_BOUNDS['south'], MALIBU_BOUNDS['west']) is True
        assert is_in_malibu(MALIBU_BOUNDS['north'], MALIBU_BOUNDS['east']) is True

    def test_just_outside_bounds(self):
        eps = 0.0001
        assert is_in_malibu(MALIBU_BOUNDS['north'] + eps, MALIBU_BOUNDS['west']) is False
        assert is_in_malibu(MALIBU_BOUNDS['south'], MALIBU_BOUNDS['west'] - eps) is False


@pytest.mark.unit
class TestIsInCoverageArea:
    """Coverage area is the union of Westside and Malibu boxes."""

    def test_westside_point(self):
        assert is_in_coverage_area(*SANTA_MONICA_PIER_COORDS) is True

    def test_malibu_point(self):
        assert is_in_coverage_area(*MALIBU_BEACH) is True

    def test_outside_point(self):
        assert is_in_coverage_area(*DOWNTOWN_LA) is False
        assert is_in_coverage_area(*PASADENA) is False


@pytest.mark.unit
class TestIsWithinCoverageRadius:
    """Radius check relative to the Santa Monica Pier reference point."""

    def test_reference_point_is_within(self):
        assert is_within_coverage_radius(*SANTA_MONICA_PIER) is True

    def test_far_point_outside_default_radius(self):
        # Pasadena is well beyond the default 12-mile radius.
        assert is_within_coverage_radius(*PASADENA) is False

    def test_custom_radius_can_include_far_point(self):
        # With a generous radius, even Pasadena qualifies.
        assert is_within_coverage_radius(*PASADENA, max_miles=100) is True


@pytest.mark.unit
class TestExtractZipCodes:
    """Test the zip-code extraction helper."""

    def test_single_zip(self):
        assert extract_zip_codes("Santa Monica, CA 90401") == ["90401"]

    def test_multiple_zips(self):
        assert extract_zip_codes("90401 and 90291") == ["90401", "90291"]

    def test_no_zip(self):
        assert extract_zip_codes("No numbers here") == []

    def test_empty_string(self):
        assert extract_zip_codes("") == []

    def test_none_input(self):
        assert extract_zip_codes(None) == []

    def test_word_boundary_excludes_longer_digit_runs(self):
        # \b\d{5}\b should not match a 6-digit run that has no 5-digit boundary.
        assert extract_zip_codes("123456") == []

    def test_extracts_five_digit_run_among_words(self):
        assert extract_zip_codes("Address: 1234 Main St 90405") == ["90405"]


@pytest.mark.unit
class TestIsWestsideAddress:
    """Text-based matching for Westside/Malibu addresses."""

    def test_city_match(self):
        assert is_westside_address("123 Main St", city="Santa Monica") is True

    def test_city_match_case_insensitive(self):
        assert is_westside_address(None, city="MALIBU") is True

    def test_neighborhood_substring_in_address(self):
        assert is_westside_address("100 Venice Blvd", city=None) is True

    def test_venue_name_neighborhood_match(self):
        assert is_westside_address(None, None, venue_name="Brentwood Theater") is True

    def test_zip_match(self):
        # 90401 is a Santa Monica Westside zip.
        assert is_westside_address("Somewhere 90401") is True

    def test_zip_not_in_coverage(self):
        # 90028 (Hollywood) is not in WESTSIDE_ZIP_CODES and has no neighborhood text.
        assert is_westside_address("Random St 90028") is False

    def test_no_match_returns_false(self):
        assert is_westside_address("123 Elsewhere Ave", city="Pasadena") is False

    def test_empty_inputs_return_false(self):
        assert is_westside_address(None, None, None) is False
        assert is_westside_address("", "", "") is False

    def test_west_hollywood_city_matches_despite_not_being_westside(self):
        # NOTE: documents current behavior. 'west hollywood' is hard-coded into the
        # city allow-list in is_westside_address even though the project geo-fence
        # (per project memory) does not consider West Hollywood part of the Westside.
        # This is asserted as the *actual* current behavior, not endorsed as correct.
        assert is_westside_address(None, city="West Hollywood") is True


@pytest.mark.unit
class TestValidateEventLocation:
    """Test the distinct return paths of validate_event_location."""

    def test_coordinates_in_bounds(self):
        valid, reason = validate_event_location(
            latitude=SANTA_MONICA_PIER_COORDS[0],
            longitude=SANTA_MONICA_PIER_COORDS[1],
        )
        assert valid is True
        assert reason == "coordinates_in_bounds"

    def test_malibu_coordinates_in_bounds(self):
        valid, reason = validate_event_location(
            latitude=MALIBU_BEACH[0], longitude=MALIBU_BEACH[1]
        )
        assert valid is True
        assert reason == "coordinates_in_bounds"

    def test_coordinates_outside_area(self):
        valid, reason = validate_event_location(
            latitude=DOWNTOWN_LA[0], longitude=DOWNTOWN_LA[1]
        )
        assert valid is False
        assert reason == "coordinates_outside_area"

    def test_coordinates_outside_box_but_address_match_near_area(self):
        # Pick a point just north of the Westside north bound (so it falls outside
        # both bounding boxes) at the pier's longitude, which keeps it well within
        # the 12-mile coverage radius. Combined with a recognized Westside address,
        # this exercises the "address_match_near_area" fallback path.
        lat = WESTSIDE_BOUNDS['north'] + 0.005  # just north of box -> outside box
        lon = SANTA_MONICA_PIER[1]              # pier longitude -> near pier
        # Confirm our chosen coords are indeed outside the coverage boxes.
        assert is_in_coverage_area(lat, lon) is False
        # And within radius of the pier.
        assert is_within_coverage_radius(lat, lon) is True
        valid, reason = validate_event_location(
            latitude=lat, longitude=lon, city="Santa Monica"
        )
        assert valid is True
        assert reason == "address_match_near_area"

    def test_address_text_match_without_coords(self):
        valid, reason = validate_event_location(city="Venice")
        assert valid is True
        assert reason == "address_text_match"

    def test_address_not_recognized_without_coords(self):
        valid, reason = validate_event_location(address="123 Elsewhere", city="Pasadena")
        assert valid is False
        assert reason == "address_not_recognized"

    def test_no_location_info(self):
        valid, reason = validate_event_location()
        assert valid is False
        assert reason == "no_location_info"

    def test_outside_coords_with_unrecognized_address(self):
        # Coordinates present and outside; address does not match -> outside.
        valid, reason = validate_event_location(
            latitude=DOWNTOWN_LA[0], longitude=DOWNTOWN_LA[1],
            address="Downtown", city="Los Angeles",
        )
        assert valid is False
        assert reason == "coordinates_outside_area"


@pytest.mark.unit
class TestGetLocationArea:
    """Test the area-classification helper."""

    def test_westside(self):
        assert get_location_area(*SANTA_MONICA_PIER_COORDS) == "westside"

    def test_malibu(self):
        assert get_location_area(*MALIBU_BEACH) == "malibu"

    def test_outside(self):
        assert get_location_area(*DOWNTOWN_LA) == "outside"
