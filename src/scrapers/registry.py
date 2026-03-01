"""
Central scraper registry used by scraper runners.
"""
from typing import Dict, List, Type

import config

from .aero_theater import AeroTheaterScraper
from .afdela import AFdelaScraper
from .apero_francophone import AperoFrancophoneScraper
from .arcana_books import ArcanaBooksScraper
from .aviator_dreamland import AviatorDreamlandScraper
from .aviator_nation import AviatorNationScraper
from .bergamot_station import BergamotStationScraper
from .beyond_baroque import BeyondBaroqueScraper
from .broad_stage import BroadStageScraper
from .brightside import BrightsideScraper
from .casual_creative import CasualCreativeScraper
from .culver_city import CulverCityScraper
from .discover_la import DiscoverLAScraper
from .eventbrite import EventbriteScraper
from .fowler_museum import FowlerMuseumScraper
from .geffen_playhouse import GeffenPlayhouseScraper
from .getty_center import GettyCenterScraper
from .getty_villa import GettyVillaScraper
from .gnarwhal import GnarwhalScraper
from .hammer import HammerScraper
from .iic_la import IICLAScraper
from .itk_la import ITKLAScraper
from .jamesons_pub import JamesonsPubScraper
from .kcrw import KCRWScraper
from .kinn import KinnScraper
from .lacma import LACMAScraper
from .laemmle_monica import LaemmleMonicaScraper
from .laist import LAistScraper
from .la_puglia import LaPugliaScraper
from .latechevents import LATechEventsScraper
from .mccabes import McCabesScraper
from .meetup import MeetupScraper
from .mudwtr import MudWtrScraper
from .nerd_nite import NerdNiteScraper
from .nuart_theatre import NuartTheatreScraper
from .old_town_music_hall import OldTownMusicHallScraper
from .papille_gustative import PapilleGustativeScraper
from .parks_ca import ParksCaliforniaScraper
from .penmar import PenmarScraper
from .raymond_kabbaz import RaymondKabbazScraper
from .recreation_cafe import RecreationCafeScraper
from .resident_advisor import ResidentAdvisorScraper
from .santa_monica import SantaMonicaScraper
from .santamonica_events import SantaMonicaEventsScraper
from .skirball import SkirballScraper
from .sm_farmers_market import SantaMonicaFarmersMarketScraper
from .sounds_like_la import SoundsLikeLAScraper
from .timeout import TimeoutScraper
from .tripp import TrippScraper
from .ucla import UCLAScraper
from .ucla_botanical import UCLABotanicalScraper
from .venice_beach import VeniceBeachScraper
from .venice_west import VeniceWestScraper
from .victorian import VictorianScraper
from .west_hollywood import WestHollywoodScraper
from .westside_comedy import WestsideComedyScraper
from .william_turner import WilliamTurnerScraper
from .winston_house import WinstonHouseScraper


SCRAPER_MAP: Dict[str, Type] = {
    'santa_monica': SantaMonicaScraper,
    'santamonica_events': SantaMonicaEventsScraper,
    'timeout': TimeoutScraper,
    'kcrw': KCRWScraper,
    'laist': LAistScraper,
    'discover_la': DiscoverLAScraper,
    'eventbrite': EventbriteScraper,
    'ucla': UCLAScraper,
    'hammer': HammerScraper,
    'lacma': LACMAScraper,
    'venice_beach': VeniceBeachScraper,
    'weho': WestHollywoodScraper,
    'culver_city': CulverCityScraper,
    'meetup': MeetupScraper,
    'venice_west': VeniceWestScraper,
    'winston_house': WinstonHouseScraper,
    'westside_comedy': WestsideComedyScraper,
    'aviator_nation': AviatorNationScraper,
    'aviator_dreamland': AviatorDreamlandScraper,
    'gnarwhal': GnarwhalScraper,
    'penmar': PenmarScraper,
    'itk_la': ITKLAScraper,
    'nerd_nite': NerdNiteScraper,
    'resident_advisor': ResidentAdvisorScraper,
    'iic_la': IICLAScraper,
    'afdela': AFdelaScraper,
    'raymond_kabbaz': RaymondKabbazScraper,
    'ucla_botanical': UCLABotanicalScraper,
    'parks_ca': ParksCaliforniaScraper,
    'kinn': KinnScraper,
    'casual_creative': CasualCreativeScraper,
    'latechevents': LATechEventsScraper,
    'beyond_baroque': BeyondBaroqueScraper,
    'apero_francophone': AperoFrancophoneScraper,
    'aero_theater': AeroTheaterScraper,
    'laemmle_monica': LaemmleMonicaScraper,
    'mudwtr': MudWtrScraper,
    'getty_center': GettyCenterScraper,
    'getty_villa': GettyVillaScraper,
    'skirball': SkirballScraper,
    'geffen_playhouse': GeffenPlayhouseScraper,
    'broad_stage': BroadStageScraper,
    'nuart_theatre': NuartTheatreScraper,
    'mccabes': McCabesScraper,
    'bergamot_station': BergamotStationScraper,
    'fowler_museum': FowlerMuseumScraper,
    'sm_farmers_market': SantaMonicaFarmersMarketScraper,
    'william_turner': WilliamTurnerScraper,
    'sounds_like_la': SoundsLikeLAScraper,
    'brightside': BrightsideScraper,
    'old_town_music_hall': OldTownMusicHallScraper,
    'tripp': TrippScraper,
    'la_puglia': LaPugliaScraper,
    'recreation_cafe': RecreationCafeScraper,
    'victorian': VictorianScraper,
    'papille_gustative': PapilleGustativeScraper,
    'jamesons_pub': JamesonsPubScraper,
    'arcana_books': ArcanaBooksScraper,
}


def get_enabled_scraper_names() -> List[str]:
    """Return registry keys enabled in config.EVENT_SOURCES."""
    return [
        name for name in SCRAPER_MAP
        if config.EVENT_SOURCES.get(name, {}).get('enabled', False)
    ]


def instantiate_scrapers(scraper_names: List[str]) -> List:
    """Instantiate scrapers from a list of registry names."""
    return [SCRAPER_MAP[name]() for name in scraper_names]


def instantiate_enabled_scrapers() -> List:
    """Instantiate all configured and enabled scrapers."""
    return instantiate_scrapers(get_enabled_scraper_names())
