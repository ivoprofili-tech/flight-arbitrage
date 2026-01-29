"""
Database module for storing flight data.

This module provides functions to save and query flight search results
using SQLite - a simple file-based database that requires no server setup.
"""

from .flights_db import (
    init_database,
    save_flight_search,
    save_flights,
    get_all_searches,
    get_flights_by_search,
    get_cheapest_flights,
    get_price_history,
    FlightDatabase
)

__all__ = [
    'init_database',
    'save_flight_search',
    'save_flights',
    'get_all_searches',
    'get_flights_by_search',
    'get_cheapest_flights',
    'get_price_history',
    'FlightDatabase'
]
