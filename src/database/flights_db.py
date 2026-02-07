"""
Flight Database Module
======================
Stores all flight search results in a local SQLite database for
historical tracking and cross-location price analysis.

TABLES:
1. searches  - One row per search invocation (route + date + timestamp)
2. flights   - Individual flight results linked to a search, including
               geo-location, currency, and flight numbers
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Default database file location
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "flights.db"


class FlightDatabase:
    """Manages the SQLite flight results database."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row

        self._create_tables()
        logger.info(f"Database initialized at: {self.db_path}")

    def _create_tables(self):
        """Create tables if they don't exist, and migrate if needed."""
        cursor = self.conn.cursor()

        # Table 1: searches - one row per search invocation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                return_date TEXT,
                search_type TEXT NOT NULL DEFAULT 'standard',
                search_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                flights_found INTEGER DEFAULT 0
            )
        ''')

        # Table 2: flights - individual results with geo + currency context
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                airline TEXT,
                flight_numbers TEXT,
                departure_time TEXT,
                arrival_time TEXT,
                duration TEXT,
                stops TEXT,
                layovers TEXT,
                source TEXT,
                location TEXT,
                location_name TEXT,
                currency TEXT,
                price_local REAL,
                price_local_str TEXT,
                price_usd REAL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (search_id) REFERENCES searches(id)
            )
        ''')

        # Indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flights_search_id
            ON flights(search_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flights_price_usd
            ON flights(price_usd)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_searches_route
            ON searches(origin, destination)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flights_location
            ON flights(location)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flights_airline_time
            ON flights(airline, departure_time)
        ''')

        self.conn.commit()

    # ------------------------------------------------------------------
    # Save methods
    # ------------------------------------------------------------------

    def save_search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        search_type: str = "standard",
        flights_found: int = 0,
    ) -> int:
        """Save a search record and return its ID."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO searches
                (origin, destination, departure_date, return_date, search_type, flights_found)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (origin, destination, departure_date, return_date, search_type, flights_found))
        self.conn.commit()
        return cursor.lastrowid

    def save_geo_flights(
        self,
        search_id: int,
        flights: list,
    ) -> int:
        """
        Save GeoFlightResult objects (or dicts with equivalent keys) to the database.

        Accepts either GeoFlightResult dataclass instances or plain dicts
        with keys: airline, flight_numbers, departure_time, arrival_time,
        duration, stops, layovers, source, location, location_name,
        currency, price_original, price_usd.
        """
        cursor = self.conn.cursor()
        saved = 0

        for f in flights:
            # Support both dataclass and dict
            if hasattr(f, "to_dict"):
                d = f.to_dict()
            elif isinstance(f, dict):
                d = f
            else:
                continue

            # Parse numeric local price from price_original string
            price_local = self._extract_price_float(d.get("price_original", ""))

            layovers_str = ", ".join(d.get("layovers", []))

            cursor.execute('''
                INSERT INTO flights (
                    search_id, airline, flight_numbers,
                    departure_time, arrival_time, duration,
                    stops, layovers, source,
                    location, location_name, currency,
                    price_local, price_local_str, price_usd
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                search_id,
                d.get("airline"),
                d.get("flight_numbers", ""),
                d.get("departure_time"),
                d.get("arrival_time"),
                d.get("duration"),
                d.get("stops"),
                layovers_str,
                d.get("source", ""),
                d.get("location", ""),
                d.get("location_name", ""),
                d.get("currency", "USD"),
                price_local,
                d.get("price_original", ""),
                d.get("price_usd"),
            ))
            saved += 1

        # Update flights_found count
        cursor.execute(
            'UPDATE searches SET flights_found = ? WHERE id = ?',
            (saved, search_id),
        )
        self.conn.commit()
        return saved

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_all_searches(self, limit: int = 50) -> list[dict]:
        """Get all search records, most recent first."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM searches
            ORDER BY search_timestamp DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_flights_by_search(self, search_id: int) -> list[dict]:
        """Get all flights for a specific search, cheapest first."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM flights
            WHERE search_id = ?
            ORDER BY price_usd ASC
        ''', (search_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_cheapest_by_route(
        self,
        origin: str,
        destination: str,
        location: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get cheapest flights for a route, optionally filtered by location."""
        cursor = self.conn.cursor()
        query = '''
            SELECT f.*, s.origin, s.destination, s.departure_date,
                   s.search_timestamp, s.search_type
            FROM flights f
            JOIN searches s ON f.search_id = s.id
            WHERE s.origin = ? AND s.destination = ?
              AND f.price_usd IS NOT NULL AND f.price_usd > 0
        '''
        params: list = [origin.upper(), destination.upper()]

        if location:
            query += ' AND f.location = ?'
            params.append(location.upper())

        query += ' ORDER BY f.price_usd ASC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_price_comparison(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
    ) -> list[dict]:
        """
        Get price comparison across locations for a route.

        Returns one row per (location, search_timestamp) with min/avg/max prices.
        """
        cursor = self.conn.cursor()
        query = '''
            SELECT
                f.location,
                f.location_name,
                f.currency,
                s.departure_date,
                s.search_timestamp,
                COUNT(f.id) as flight_count,
                MIN(f.price_usd) as min_price_usd,
                AVG(f.price_usd) as avg_price_usd,
                MAX(f.price_usd) as max_price_usd,
                MIN(f.price_local) as min_price_local,
                AVG(f.price_local) as avg_price_local
            FROM flights f
            JOIN searches s ON f.search_id = s.id
            WHERE s.origin = ? AND s.destination = ?
              AND f.price_usd IS NOT NULL AND f.price_usd > 0
        '''
        params: list = [origin.upper(), destination.upper()]

        if departure_date:
            query += ' AND s.departure_date = ?'
            params.append(departure_date)

        query += '''
            GROUP BY f.location, s.search_timestamp
            ORDER BY s.search_timestamp DESC, min_price_usd ASC
        '''

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_price_history(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
    ) -> list[dict]:
        """Get price history for a route across all searches."""
        cursor = self.conn.cursor()
        query = '''
            SELECT
                s.search_timestamp,
                s.departure_date,
                f.location,
                MIN(f.price_usd) as min_price,
                AVG(f.price_usd) as avg_price,
                COUNT(f.id) as flight_count
            FROM searches s
            JOIN flights f ON f.search_id = s.id
            WHERE s.origin = ? AND s.destination = ?
              AND f.price_usd IS NOT NULL AND f.price_usd > 0
        '''
        params: list = [origin.upper(), destination.upper()]

        if departure_date:
            query += ' AND s.departure_date = ?'
            params.append(departure_date)

        query += '''
            GROUP BY s.id, f.location
            ORDER BY s.search_timestamp DESC
        '''

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_price_float(price_str: str) -> Optional[float]:
        """Extract numeric value from a price string like '$226' or 'BRL 1179'."""
        if not price_str:
            return None
        import re
        match = re.search(r'[\d,.]+', price_str)
        if match:
            num_str = match.group().replace(',', '')
            try:
                return float(num_str)
            except ValueError:
                return None
        return None

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_default_db: Optional[FlightDatabase] = None


def _get_db() -> FlightDatabase:
    """Get the default database, initializing if needed."""
    global _default_db
    if _default_db is None:
        _default_db = FlightDatabase()
    return _default_db


def save_geo_search(
    origin: str,
    destination: str,
    departure_date: str,
    location_results: dict,
    return_date: Optional[str] = None,
) -> int:
    """
    Save a complete geo arbitrage search to the database.

    Args:
        origin: Origin airport code
        destination: Destination airport code
        departure_date: Departure date
        location_results: Dict of {location: LocationSearchResult}
        return_date: Optional return date

    Returns:
        The search ID
    """
    db = _get_db()

    # Count total flights across all locations
    total_flights = sum(
        len(lr.flights) for lr in location_results.values() if hasattr(lr, 'flights')
    )

    search_id = db.save_search(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        search_type="geo_arbitrage",
        flights_found=total_flights,
    )

    # Save flights from each location
    all_flights = []
    for loc, lr in location_results.items():
        if hasattr(lr, 'flights'):
            all_flights.extend(lr.flights)

    saved = db.save_geo_flights(search_id, all_flights)
    logger.info(f"Saved search #{search_id}: {saved} flights across {len(location_results)} locations")

    return search_id
