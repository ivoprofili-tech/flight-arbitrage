# Flight scraper module
# This file makes the scraper folder a Python "package"

from .google_flights import GoogleFlightsScraper, search_google_flights, save_results_to_file
from .skyscanner import SkyscannerScraper, search_skyscanner_flights
from .kayak import KayakScraper, search_kayak_flights
from .skiplagged import SkiplaggedScraper, search_skiplagged_flights

__all__ = [
    'GoogleFlightsScraper',
    'search_google_flights',
    'save_results_to_file',
    'SkyscannerScraper',
    'search_skyscanner_flights',
    'KayakScraper',
    'search_kayak_flights',
    'SkiplaggedScraper',
    'search_skiplagged_flights'
]
