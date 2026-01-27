# Flight scraper module
# This file makes the scraper folder a Python "package"

from .google_flights import GoogleFlightsScraper, search_google_flights

__all__ = ['GoogleFlightsScraper', 'search_google_flights']
