#!/usr/bin/env python3
"""
Search multiple flight sources (Google Flights & Skyscanner).

Usage:
    python scripts/search_all.py "New York" "Los Angeles" 2025-03-01
    python scripts/search_all.py "New York" "Los Angeles" 2025-03-01 --source google
    python scripts/search_all.py "New York" "Los Angeles" 2025-03-01 --source skyscanner
    python scripts/search_all.py "New York" "Los Angeles" 2025-03-01 2025-03-08

Arguments:
    origin       - Departure city (e.g., "New York", "JFK")
    destination  - Arrival city (e.g., "Los Angeles", "LAX")
    departure    - Departure date (YYYY-MM-DD format)
    return       - Optional return date (YYYY-MM-DD format)

Options:
    --source     - Search only specific source: "google", "skyscanner", or "all" (default)

Results are saved to:
    - Text files in the current directory
    - SQLite database at data/flights.db
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import search_google_flights, search_skyscanner_flights, save_results_to_file
from src.database import save_flight_search


def print_flights(flights: list[dict], source: str):
    """Print flight results to console."""
    print(f"\n{'=' * 50}")
    print(f"{source}: Found {len(flights)} flights")
    print("=" * 50)

    for i, flight in enumerate(flights, 1):
        print(f"\n[{i}] {flight.get('airline', 'Unknown Airline')}")
        print(f"    Price: {flight.get('price', 'N/A')}")
        print(f"    Depart: {flight.get('departure_time', 'N/A')} → Arrive: {flight.get('arrival_time', 'N/A')}")
        print(f"    Duration: {flight.get('duration', 'N/A')} | Stops: {flight.get('stops', 'N/A')}")


async def search_google(origin, destination, departure_date, return_date):
    """Search Google Flights."""
    print("\n" + "=" * 60)
    print("SEARCHING GOOGLE FLIGHTS...")
    print("=" * 60)

    try:
        flights = await search_google_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            headless=True
        )

        # Add source tag
        for flight in flights:
            flight['source'] = 'Google Flights'

        return flights
    except Exception as e:
        print(f"Google Flights search failed: {e}")
        return []


async def search_skyscanner(origin, destination, departure_date, return_date):
    """Search Skyscanner."""
    print("\n" + "=" * 60)
    print("SEARCHING SKYSCANNER...")
    print("=" * 60)

    try:
        flights = await search_skyscanner_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            headless=True
        )

        return flights
    except Exception as e:
        print(f"Skyscanner search failed: {e}")
        return []


async def main():
    # Parse command line arguments
    if len(sys.argv) < 4:
        print(__doc__)
        print("Error: Not enough arguments!")
        print("\nExample:")
        print('  python scripts/search_all.py "New York" "Los Angeles" 2025-03-01')
        sys.exit(1)

    # Parse positional arguments
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    origin = args[0]
    destination = args[1]
    departure_date = args[2]
    return_date = args[3] if len(args) > 3 else None

    # Parse options
    source = "all"
    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i + 1 < len(sys.argv):
            source = sys.argv[i + 1].lower()

    print("=" * 60)
    print("MULTI-SOURCE FLIGHT SEARCH")
    print("=" * 60)
    print(f"From: {origin}")
    print(f"To: {destination}")
    print(f"Departure: {departure_date}")
    if return_date:
        print(f"Return: {return_date}")
    else:
        print("Type: One-way")
    print(f"Sources: {source}")
    print("=" * 60)

    all_flights = []

    # Search based on source selection
    if source in ["all", "google"]:
        google_flights = await search_google(origin, destination, departure_date, return_date)
        if google_flights:
            print_flights(google_flights, "Google Flights")
            all_flights.extend(google_flights)

    if source in ["all", "skyscanner"]:
        skyscanner_flights = await search_skyscanner(origin, destination, departure_date, return_date)
        if skyscanner_flights:
            print_flights(skyscanner_flights, "Skyscanner")
            all_flights.extend(skyscanner_flights)

    # Save combined results
    if all_flights:
        # Sort all flights by price
        all_flights.sort(key=lambda x: int(''.join(c for c in x.get('price', '999999') if c.isdigit()) or '999999'))

        # Save to file
        filename = save_results_to_file(
            flights=all_flights,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date
        )

        # Save to database
        search_id = save_flight_search(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            flights=all_flights
        )

        # Print summary
        print("\n" + "=" * 60)
        print("COMBINED RESULTS SUMMARY")
        print("=" * 60)
        print(f"Total flights found: {len(all_flights)}")

        # Count by source
        google_count = len([f for f in all_flights if f.get('source') == 'Google Flights'])
        skyscanner_count = len([f for f in all_flights if f.get('source') == 'Skyscanner'])
        print(f"  Google Flights: {google_count}")
        print(f"  Skyscanner: {skyscanner_count}")

        # Show top 5 cheapest
        print("\nTop 5 Cheapest:")
        for i, flight in enumerate(all_flights[:5], 1):
            print(f"  {i}. {flight.get('price')} - {flight.get('airline')} ({flight.get('source')})")

        print(f"\nResults saved to: {filename}")
        print(f"Database search ID: #{search_id}")
    else:
        print("\nNo flights found from any source.")

    return all_flights


if __name__ == "__main__":
    asyncio.run(main())
