#!/usr/bin/env python3
"""
Query the flight database.

Usage:
    python scripts/query_db.py searches              # List all searches
    python scripts/query_db.py flights <search_id>   # Show flights for a search
    python scripts/query_db.py cheapest              # Show cheapest flights
    python scripts/query_db.py cheapest "New York" "Los Angeles"  # Filter by route
    python scripts/query_db.py history "New York" "Los Angeles"   # Price history
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import (
    get_all_searches,
    get_flights_by_search,
    get_cheapest_flights,
    get_price_history
)


def show_searches():
    """Display all searches."""
    searches = get_all_searches()

    if not searches:
        print("No searches found in database.")
        return

    print("\n" + "=" * 70)
    print("SAVED SEARCHES")
    print("=" * 70)

    for s in searches:
        print(f"\n[#{s['id']}] {s['origin']} → {s['destination']}")
        print(f"     Date: {s['departure_date']}")
        print(f"     Searched: {s['search_timestamp']}")
        print(f"     Flights found: {s['flights_found']}")


def show_flights(search_id: int):
    """Display flights for a specific search."""
    flights = get_flights_by_search(search_id)

    if not flights:
        print(f"No flights found for search #{search_id}")
        return

    print("\n" + "=" * 70)
    print(f"FLIGHTS FOR SEARCH #{search_id}")
    print("=" * 70)

    for i, f in enumerate(flights, 1):
        print(f"\n[{i}] {f['airline']}")
        print(f"    Price: {f['price']}")
        print(f"    Depart: {f['departure_time']} → Arrive: {f['arrival_time']}")
        print(f"    Duration: {f['duration']} | Stops: {f['stops']}")


def show_cheapest(origin: str = None, destination: str = None):
    """Display cheapest flights."""
    flights = get_cheapest_flights(origin, destination)

    if not flights:
        print("No flights found in database.")
        return

    title = "CHEAPEST FLIGHTS"
    if origin and destination:
        title += f" ({origin} → {destination})"

    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    for i, f in enumerate(flights, 1):
        print(f"\n[{i}] {f['price']} - {f['airline']}")
        print(f"    Route: {f['origin']} → {f['destination']}")
        print(f"    Date: {f['departure_date']}")
        print(f"    Time: {f['departure_time']} → {f['arrival_time']}")


def show_history(origin: str, destination: str):
    """Display price history for a route."""
    history = get_price_history(origin, destination)

    if not history:
        print(f"No price history found for {origin} → {destination}")
        return

    print("\n" + "=" * 70)
    print(f"PRICE HISTORY: {origin} → {destination}")
    print("=" * 70)

    for h in history:
        print(f"\n{h['search_timestamp']}")
        print(f"  Departure: {h['departure_date']}")
        print(f"  Min: ${h['min_price']} | Max: ${h['max_price']} | Avg: ${int(h['avg_price'])}")
        print(f"  Flights: {h['flight_count']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "searches":
        show_searches()

    elif command == "flights":
        if len(sys.argv) < 3:
            print("Usage: python scripts/query_db.py flights <search_id>")
            sys.exit(1)
        show_flights(int(sys.argv[2]))

    elif command == "cheapest":
        origin = sys.argv[2] if len(sys.argv) > 2 else None
        destination = sys.argv[3] if len(sys.argv) > 3 else None
        show_cheapest(origin, destination)

    elif command == "history":
        if len(sys.argv) < 4:
            print("Usage: python scripts/query_db.py history <origin> <destination>")
            sys.exit(1)
        show_history(sys.argv[2], sys.argv[3])

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
