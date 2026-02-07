# Flight scraper module
# This file makes the scraper folder a Python "package"
#
# Google Flights: Uses SerpApi (structured JSON API, no browser needed)
# Skiplagged: Still uses Playwright browser automation

from .google_flights_serpapi import search_google_flights, save_results_to_file
from .skiplagged import SkiplaggedScraper, search_skiplagged_flights

__all__ = [
    'search_google_flights',
    'save_results_to_file',
    'SkiplaggedScraper',
    'search_skiplagged_flights',
]
