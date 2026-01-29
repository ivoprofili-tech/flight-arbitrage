"""
Flight Database Module
======================
This module handles all database operations for storing flight search results.

DATABASE CONCEPTS:
- SQLite: A lightweight database stored in a single file
- Tables: Like spreadsheets, they store related data in rows and columns
- Primary Key: A unique identifier for each row (like an ID number)
- Foreign Key: Links data between tables (search_id links flights to searches)

TABLES:
1. searches - Records each search you perform
2. flights - Stores individual flight results linked to searches
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


# Default database file location
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "flights.db"


class FlightDatabase:
    """
    A class to manage the flight database.

    Using a class allows us to:
    - Keep the database connection open for multiple operations
    - Ensure proper cleanup when we're done
    - Organize related functions together
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file.
                     If not provided, uses default location.
        """
        if db_path is None:
            db_path = DEFAULT_DB_PATH

        self.db_path = Path(db_path)

        # Create the data directory if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to the database (creates file if it doesn't exist)
        self.conn = sqlite3.connect(str(self.db_path))

        # Enable foreign key support
        self.conn.execute("PRAGMA foreign_keys = ON")

        # Return rows as dictionaries instead of tuples (easier to work with)
        self.conn.row_factory = sqlite3.Row

        # Create tables if they don't exist
        self._create_tables()

        print(f"Database initialized at: {self.db_path}")

    def _create_tables(self):
        """
        Create the database tables if they don't exist.

        SQL CREATE TABLE syntax:
        - Column definitions: name TYPE constraints
        - PRIMARY KEY: Unique identifier for each row
        - NOT NULL: Value cannot be empty
        - DEFAULT: Automatic value if not provided
        """
        cursor = self.conn.cursor()

        # Table 1: searches - Records each search performed
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                return_date TEXT,
                search_timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                flights_found INTEGER DEFAULT 0
            )
        ''')

        # Table 2: flights - Individual flight results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                airline TEXT,
                departure_time TEXT,
                arrival_time TEXT,
                duration TEXT,
                stops TEXT,
                price TEXT NOT NULL,
                price_numeric INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (search_id) REFERENCES searches(id)
            )
        ''')

        # Create indexes for faster queries
        # Indexes are like a book's index - they help find data quickly
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flights_search_id
            ON flights(search_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_flights_price
            ON flights(price_numeric)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_searches_route
            ON searches(origin, destination)
        ''')

        self.conn.commit()

    def save_search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        flights_found: int = 0
    ) -> int:
        """
        Save a search record and return its ID.

        Args:
            origin: Departure city/airport
            destination: Arrival city/airport
            departure_date: Date of departure (YYYY-MM-DD)
            return_date: Optional return date
            flights_found: Number of flights found

        Returns:
            The ID of the newly created search record
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO searches (origin, destination, departure_date, return_date, flights_found)
            VALUES (?, ?, ?, ?, ?)
        ''', (origin, destination, departure_date, return_date, flights_found))

        self.conn.commit()
        return cursor.lastrowid

    def save_flights(self, search_id: int, flights: list[dict]) -> int:
        """
        Save multiple flight records linked to a search.

        Args:
            search_id: The ID of the search these flights belong to
            flights: List of flight dictionaries from the scraper

        Returns:
            Number of flights saved
        """
        cursor = self.conn.cursor()
        saved_count = 0

        for flight in flights:
            # Extract numeric price for sorting/filtering
            price_str = flight.get('price', '')
            price_numeric = self._extract_price_number(price_str)

            cursor.execute('''
                INSERT INTO flights (
                    search_id, airline, departure_time, arrival_time,
                    duration, stops, price, price_numeric
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                search_id,
                flight.get('airline'),
                flight.get('departure_time'),
                flight.get('arrival_time'),
                flight.get('duration'),
                flight.get('stops'),
                price_str,
                price_numeric
            ))
            saved_count += 1

        # Update the flights_found count in the search record
        cursor.execute('''
            UPDATE searches SET flights_found = ? WHERE id = ?
        ''', (saved_count, search_id))

        self.conn.commit()
        return saved_count

    def _extract_price_number(self, price_str: str) -> Optional[int]:
        """
        Extract numeric value from price string.

        Examples:
            "$95" -> 95
            "$1,234" -> 1234
            "US$ 500" -> 500
        """
        if not price_str:
            return None

        # Remove everything except digits
        digits = ''.join(c for c in price_str if c.isdigit())

        return int(digits) if digits else None

    def get_all_searches(self, limit: int = 50) -> list[dict]:
        """
        Get all search records, most recent first.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of search records as dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM searches
            ORDER BY search_timestamp DESC
            LIMIT ?
        ''', (limit,))

        return [dict(row) for row in cursor.fetchall()]

    def get_flights_by_search(self, search_id: int) -> list[dict]:
        """
        Get all flights for a specific search.

        Args:
            search_id: The ID of the search

        Returns:
            List of flight records as dictionaries
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM flights
            WHERE search_id = ?
            ORDER BY price_numeric ASC
        ''', (search_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_cheapest_flights(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        limit: int = 20
    ) -> list[dict]:
        """
        Get the cheapest flights, optionally filtered by route.

        Args:
            origin: Filter by departure city (optional)
            destination: Filter by arrival city (optional)
            limit: Maximum number of results

        Returns:
            List of cheapest flights with search info
        """
        cursor = self.conn.cursor()

        query = '''
            SELECT
                f.*,
                s.origin,
                s.destination,
                s.departure_date,
                s.search_timestamp
            FROM flights f
            JOIN searches s ON f.search_id = s.id
            WHERE f.price_numeric IS NOT NULL
        '''
        params = []

        if origin:
            query += ' AND LOWER(s.origin) LIKE LOWER(?)'
            params.append(f'%{origin}%')

        if destination:
            query += ' AND LOWER(s.destination) LIKE LOWER(?)'
            params.append(f'%{destination}%')

        query += ' ORDER BY f.price_numeric ASC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_price_history(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None
    ) -> list[dict]:
        """
        Get price history for a specific route.

        Useful for tracking how prices change over time.

        Args:
            origin: Departure city
            destination: Arrival city
            departure_date: Optional specific date to track

        Returns:
            List of historical price data
        """
        cursor = self.conn.cursor()

        query = '''
            SELECT
                s.search_timestamp,
                s.departure_date,
                MIN(f.price_numeric) as min_price,
                MAX(f.price_numeric) as max_price,
                AVG(f.price_numeric) as avg_price,
                COUNT(f.id) as flight_count
            FROM searches s
            JOIN flights f ON f.search_id = s.id
            WHERE LOWER(s.origin) LIKE LOWER(?)
              AND LOWER(s.destination) LIKE LOWER(?)
              AND f.price_numeric IS NOT NULL
        '''
        params = [f'%{origin}%', f'%{destination}%']

        if departure_date:
            query += ' AND s.departure_date = ?'
            params.append(departure_date)

        query += '''
            GROUP BY s.id
            ORDER BY s.search_timestamp DESC
        '''

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

    def __enter__(self):
        """Support 'with' statement for automatic cleanup."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Automatically close connection when exiting 'with' block."""
        self.close()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
# These functions provide a simpler interface without managing the class

_default_db: Optional[FlightDatabase] = None


def init_database(db_path: Optional[str] = None) -> FlightDatabase:
    """
    Initialize the default database connection.

    Args:
        db_path: Optional custom path for the database file

    Returns:
        The FlightDatabase instance
    """
    global _default_db
    _default_db = FlightDatabase(db_path)
    return _default_db


def _get_db() -> FlightDatabase:
    """Get the default database, initializing if needed."""
    global _default_db
    if _default_db is None:
        _default_db = FlightDatabase()
    return _default_db


def save_flight_search(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    flights: Optional[list[dict]] = None
) -> int:
    """
    Save a complete flight search with all results.

    This is the main function you'll use to save scraper results.

    Args:
        origin: Departure city
        destination: Arrival city
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Optional return date
        flights: List of flight dictionaries from the scraper

    Returns:
        The search ID

    Example:
        search_id = save_flight_search(
            origin="New York",
            destination="Los Angeles",
            departure_date="2025-03-01",
            flights=scraper_results
        )
    """
    db = _get_db()

    # Save the search record
    search_id = db.save_search(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        flights_found=len(flights) if flights else 0
    )

    # Save the flights if provided
    if flights:
        db.save_flights(search_id, flights)

    print(f"Saved search #{search_id} with {len(flights) if flights else 0} flights")
    return search_id


def save_flights(search_id: int, flights: list[dict]) -> int:
    """Save flights for an existing search."""
    return _get_db().save_flights(search_id, flights)


def get_all_searches(limit: int = 50) -> list[dict]:
    """Get all search records."""
    return _get_db().get_all_searches(limit)


def get_flights_by_search(search_id: int) -> list[dict]:
    """Get flights for a specific search."""
    return _get_db().get_flights_by_search(search_id)


def get_cheapest_flights(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    limit: int = 20
) -> list[dict]:
    """Get cheapest flights, optionally filtered by route."""
    return _get_db().get_cheapest_flights(origin, destination, limit)


def get_price_history(
    origin: str,
    destination: str,
    departure_date: Optional[str] = None
) -> list[dict]:
    """Get price history for a route."""
    return _get_db().get_price_history(origin, destination, departure_date)


# ============================================================================
# TEST CODE
# ============================================================================
if __name__ == "__main__":
    # Test the database functionality
    print("=" * 60)
    print("FLIGHT DATABASE TEST")
    print("=" * 60)

    # Use a test database
    with FlightDatabase("test_flights.db") as db:
        # Save a test search
        search_id = db.save_search(
            origin="New York",
            destination="Los Angeles",
            departure_date="2025-03-01"
        )
        print(f"\nCreated search with ID: {search_id}")

        # Save some test flights
        test_flights = [
            {
                'airline': 'Spirit',
                'departure_time': '6:00 AM',
                'arrival_time': '9:28 AM',
                'duration': '6h 28m',
                'stops': 'Nonstop',
                'price': '$95'
            },
            {
                'airline': 'United',
                'departure_time': '8:00 AM',
                'arrival_time': '11:15 AM',
                'duration': '6h 15m',
                'stops': 'Nonstop',
                'price': '$150'
            }
        ]

        saved = db.save_flights(search_id, test_flights)
        print(f"Saved {saved} flights")

        # Query the data
        print("\nAll searches:")
        for search in db.get_all_searches():
            print(f"  #{search['id']}: {search['origin']} -> {search['destination']} ({search['flights_found']} flights)")

        print("\nFlights for search #1:")
        for flight in db.get_flights_by_search(search_id):
            print(f"  {flight['airline']}: {flight['price']} ({flight['departure_time']} - {flight['arrival_time']})")

        print("\nCheapest flights:")
        for flight in db.get_cheapest_flights(limit=5):
            print(f"  {flight['price']} - {flight['origin']} to {flight['destination']}")

    # Clean up test database
    import os
    os.remove("test_flights.db")
    print("\nTest database cleaned up.")
    print("Database module is working correctly!")
