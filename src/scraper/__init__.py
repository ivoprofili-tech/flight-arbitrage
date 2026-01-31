# Flight scraper module
# This file makes the scraper folder a Python "package"

from .google_flights import GoogleFlightsScraper, search_google_flights, save_results_to_file
from .skiplagged import SkiplaggedScraper, search_skiplagged_flights

__all__ = [
    'GoogleFlightsScraper',
    'search_google_flights',
    'save_results_to_file',
    'SkiplaggedScraper',
    'search_skiplagged_flights'
]
