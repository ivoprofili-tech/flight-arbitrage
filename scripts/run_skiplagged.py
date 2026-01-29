#!/usr/bin/env python3
"""
Search Skiplagged for flights.

Usage:
    python scripts/run_skiplagged.py JFK LAX 2025-03-01
    python scripts/run_skiplagged.py "New York" "Los Angeles" 2025-03-01

Arguments:
    origin       - Departure airport code or city (e.g., "JFK", "New York")
    destination  - Arrival airport code or city (e.g., "LAX", "Los Angeles")
    departure    - Departure date (YYYY-MM-DD format)
    return       - Optional return date (YYYY-MM-DD format)

Results are saved to:
    - A text file in the current directory
    - SQLite database at data/flights.db
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper.skiplagged import search_skiplagged_flights
from src.scraper import save_results_to_file
from src.database import save_flight_search


async def main():
    if len(sys.argv) < 4:
        print(__doc__)
        print("Error: Not enough arguments!")
        print("\nExample:")
        print('  python scripts/run_skiplagged.py JFK LAX 2025-03-01')
        sys.exit(1)

    origin = sys.argv[1]
    destination = sys.argv[2]
    departure_date = sys.argv[3]
    return_date = sys.argv[4] if len(sys.argv) > 4 else None

    print("=" * 50)
    print("SKIPLAGGED FLIGHT SEARCH")
    print("=" * 50)
    print(f"From: {origin}")
    print(f"To: {destination}")
    print(f"Departure: {departure_date}")
    if return_date:
        print(f"Return: {return_date}")
    else:
        print("Type: One-way")
    print("=" * 50)
    print()

    flights = await search_skiplagged_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        headless=True
    )

    if flights and not flights[0].get('error'):
        filename = save_results_to_file(
            flights=flights,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            filename=f"skiplagged_{origin}_to_{destination}.txt"
        )

        search_id = save_flight_search(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            flights=flights
        )
        print(f"Results saved to database (search #{search_id})")

        print("\n" + "=" * 50)
        print(f"Found {len(flights)} flights:")
        print("=" * 50)

        for i, flight in enumerate(flights, 1):
            print(f"\n[{i}] {flight.get('airline', 'Unknown Airline')}")
            print(f"    Price: {flight.get('price', 'N/A')}")
            print(f"    Depart: {flight.get('departure_time', 'N/A')} → Arrive: {flight.get('arrival_time', 'N/A')}")
            print(f"    Duration: {flight.get('duration', 'N/A')} | Stops: {flight.get('stops', 'N/A')}")
    else:
        print("\nNo flights found or bot detection triggered.")
        if flights and flights[0].get('error'):
            print(f"Error: {flights[0].get('error')}")

    return flights


if __name__ == "__main__":
    asyncio.run(main())
