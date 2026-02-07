"""
Database module for storing flight data.

Provides functions to save and query flight search results
using SQLite - a simple file-based database (no server needed).
"""

from .flights_db import (
    FlightDatabase,
    save_geo_search,
    _get_db,
)

__all__ = [
    'FlightDatabase',
    'save_geo_search',
]
