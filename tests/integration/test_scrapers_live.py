"""
Live integration tests for all scrapers.

These tests hit real websites to verify scrapers can still fetch and parse data.
Run with: micromamba run -n la python -m pytest tests/integration/test_scrapers_live.py -v
Run a single scraper: micromamba run -n la python -m pytest tests/integration/test_scrapers_live.py -v -k "santa_monica"
Skip Playwright scrapers: micromamba run -n la python -m pytest tests/integration/test_scrapers_live.py -v -m "not playwright"
"""
import warnings
import pytest
from src.data.models import Event


# ---------------------------------------------------------------------------
# Scraper registry – (module_path, class_name, source_name, needs_playwright)
# ---------------------------------------------------------------------------
HTTP_SCRAPERS = [
    ("src.scrapers.aero_theater", "AeroTheaterScraper", "Aero Theater"),
    ("src.scrapers.afdela", "AFdelaScraper", "AFdela"),
    ("src.scrapers.aviator_dreamland", "AviatorDreamlandScraper", "Aviator Nation Dreamland"),
    ("src.scrapers.aviator_nation", "AviatorNationScraper", "Aviator Nation"),
    ("src.scrapers.bergamot_station", "BergamotStationScraper", "Bergamot Station"),
    ("src.scrapers.brightside", "BrightsideScraper", "Brightside"),
    ("src.scrapers.culver_city", "CulverCityScraper", "Culver City"),
    ("src.scrapers.discover_la", "DiscoverLAScraper", "Discover LA"),
    ("src.scrapers.fowler_museum", "FowlerMuseumScraper", "Fowler Museum"),
    ("src.scrapers.geffen_playhouse", "GeffenPlayhouseScraper", "Geffen Playhouse"),
    ("src.scrapers.getty_center", "GettyCenterScraper", "Getty Center"),
    ("src.scrapers.getty_villa", "GettyVillaScraper", "Getty Villa"),
    ("src.scrapers.gnarwhal", "GnarwhalScraper", "Gnarwhal Coffee"),
    ("src.scrapers.hammer", "HammerScraper", "Hammer Museum"),
    ("src.scrapers.iic_la", "IICLAScraper", "IIC Los Angeles"),
    ("src.scrapers.itk_la", "ITKLAScraper", "ITK LA"),
    ("src.scrapers.jamesons_pub", "JamesonsPubScraper", "Jameson's Pub"),
    ("src.scrapers.kcrw", "KCRWScraper", "KCRW"),
    ("src.scrapers.la_puglia", "LaPugliaScraper", "La Puglia"),
    ("src.scrapers.lacma", "LACMAScraper", "LACMA"),
    ("src.scrapers.laemmle_monica", "LaemmleMonicaScraper", "Laemmle Monica Film Center"),
    ("src.scrapers.laist", "LAistScraper", "LAist"),
    ("src.scrapers.latechevents", "LATechEventsScraper", "LA Tech Events"),
    ("src.scrapers.mccabes", "McCabesScraper", "McCabe's Guitar Shop"),
    ("src.scrapers.meetup", "MeetupScraper", "Meetup"),
    ("src.scrapers.mudwtr", "MudWtrScraper", "MUD\\WTR"),
    ("src.scrapers.nerd_nite", "NerdNiteScraper", "Nerd Nite LA"),
    ("src.scrapers.old_town_music_hall", "OldTownMusicHallScraper", "Old Town Music Hall"),
    ("src.scrapers.papille_gustative", "PapilleGustativeScraper", "Papille Gustative"),
    ("src.scrapers.parks_ca", "ParksCaliforniaScraper", "California State Parks"),
    ("src.scrapers.penmar", "PenmarScraper", "The Penmar"),
    ("src.scrapers.raymond_kabbaz", "RaymondKabbazScraper", "Raymond Kabbaz"),
    ("src.scrapers.recreation_cafe", "RecreationCafeScraper", "Recreation Cafe"),
    ("src.scrapers.santa_monica", "SantaMonicaScraper", "Santa Monica"),
    ("src.scrapers.skirball", "SkirballScraper", "Skirball Cultural Center"),
    ("src.scrapers.sm_farmers_market", "SantaMonicaFarmersMarketScraper", "SM Farmers Market"),
    ("src.scrapers.sounds_like_la", "SoundsLikeLAScraper", "Sounds Like LA"),
    ("src.scrapers.timeout", "TimeoutScraper", "Timeout LA"),
    ("src.scrapers.tripp", "TrippScraper", "Tripp"),
    ("src.scrapers.ucla_botanical", "UCLABotanicalScraper", "UCLA Botanical"),
    ("src.scrapers.venice_beach", "VeniceBeachScraper", "Venice Beach Events"),
    ("src.scrapers.victorian", "VictorianScraper", "The Victorian"),
    ("src.scrapers.william_turner", "WilliamTurnerScraper", "William Turner Gallery"),
    ("src.scrapers.winston_house", "WinstonHouseScraper", "Winston House"),
]

JS_SCRAPERS = [
    ("src.scrapers.apero_francophone", "AperoFrancophoneScraper", "Apero Francophone"),
    ("src.scrapers.beyond_baroque", "BeyondBaroqueScraper", "Beyond Baroque"),
    ("src.scrapers.broad_stage", "BroadStageScraper", "The Broad Stage"),
    ("src.scrapers.casual_creative", "CasualCreativeScraper", "The Casual Creative"),
    ("src.scrapers.eventbrite", "EventbriteScraper", "Eventbrite"),
    ("src.scrapers.kinn", "KinnScraper", "KINN"),
    ("src.scrapers.nuart_theatre", "NuartTheatreScraper", "Nuart Theatre"),
    ("src.scrapers.resident_advisor", "ResidentAdvisorScraper", "Resident Advisor"),
    ("src.scrapers.ucla", "UCLAScraper", "UCLA"),
    ("src.scrapers.venice_west", "VeniceWestScraper", "Venice West"),
    ("src.scrapers.west_hollywood", "WestHollywoodScraper", "West Hollywood"),
    ("src.scrapers.westside_comedy", "WestsideComedyScraper", "Westside Comedy"),
]


def _import_scraper(module_path: str, class_name: str):
    """Dynamically import a scraper class."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _make_id(entry):
    """Create a readable test ID from a scraper entry."""
    return entry[2]  # source_name


# ---------------------------------------------------------------------------
# HTTP scraper tests (no Playwright required)
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.scraper
@pytest.mark.requires_network
@pytest.mark.parametrize(
    "module_path, class_name, source_name",
    HTTP_SCRAPERS,
    ids=[e[2] for e in HTTP_SCRAPERS],
)
def test_http_scraper_live(module_path, class_name, source_name):
    """Verify an HTTP-based scraper can fetch and return events from the real site."""
    cls = _import_scraper(module_path, class_name)
    scraper = cls()
    events = scraper.scrape()

    # Must return a list
    assert isinstance(events, list), f"{source_name}: scrape() did not return a list"

    # Every item must be an Event
    for ev in events:
        assert isinstance(ev, Event), f"{source_name}: got {type(ev)} instead of Event"

    # Warn when a scraper returns nothing — may indicate a broken scraper
    if len(events) == 0:
        warnings.warn(f"{source_name}: returned 0 events — site may have changed or is rate-limiting")


# ---------------------------------------------------------------------------
# Playwright (JS) scraper tests
# ---------------------------------------------------------------------------
@pytest.mark.integration
@pytest.mark.scraper
@pytest.mark.requires_network
@pytest.mark.playwright
@pytest.mark.parametrize(
    "module_path, class_name, source_name",
    JS_SCRAPERS,
    ids=[e[2] for e in JS_SCRAPERS],
)
def test_js_scraper_live(module_path, class_name, source_name):
    """Verify a Playwright-based scraper can fetch and return events from the real site."""
    cls = _import_scraper(module_path, class_name)
    scraper = cls()
    events = scraper.scrape()

    assert isinstance(events, list), f"{source_name}: scrape() did not return a list"

    for ev in events:
        assert isinstance(ev, Event), f"{source_name}: got {type(ev)} instead of Event"

    if len(events) == 0:
        warnings.warn(f"{source_name}: returned 0 events — site may have changed or is rate-limiting")
