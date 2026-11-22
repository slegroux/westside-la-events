"""
Unit tests for the Los Feliz 3 scraper.

The parser is shared with the Egyptian Theatre and Aero (see
test_egyptian_theatre_scraper.py); this file pins what is specific to Los Feliz.
"""
import pytest

import config
from src.scrapers.aero_theater import LosFeliz3Scraper
from src.scrapers.registry import SCRAPER_MAP
from src.utils.geo_filter import is_in_coverage_area


@pytest.mark.unit
def test_los_feliz_is_registered_and_configured():
    assert SCRAPER_MAP['los_feliz_3'] is LosFeliz3Scraper
    entry = config.EVENT_SOURCES['los_feliz_3']
    assert entry['enabled'] and entry['region'] == 'beyond'


@pytest.mark.unit
def test_los_feliz_constants_are_outside_the_westside_box():
    assert LosFeliz3Scraper.LOCATION_ID == 102
    assert LosFeliz3Scraper.REGION == 'beyond'
    assert not is_in_coverage_area(LosFeliz3Scraper.LATITUDE, LosFeliz3Scraper.LONGITUDE)
