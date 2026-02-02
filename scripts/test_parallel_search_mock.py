#!/usr/bin/env python3
"""
Mock test for parallel flight search logic.

Tests the integration without requiring actual browser/scraper execution.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Mock flight data
MOCK_GOOGLE_FLIGHTS = [
    {
        "airline": "United",
        "departure_time": "08:00",
        "arrival_time": "14:30",
        "duration": "6h 30m",
        "stops": "Nonstop",
        "price": "$450",
        "layovers": [],
    },
    {
        "airline": "Delta",
        "departure_time": "10:15",
        "arrival_time": "18:45",
        "duration": "8h 30m",
        "stops": "1 stop",
        "price": "$380",
        "layovers": ["ATL"],
    },
]

MOCK_SKIPLAGGED_FLIGHTS = [
    {
        "airline": "American",
        "departure_time": "09:00",
        "arrival_time": "15:00",
        "duration": "6h",
        "stops": "Nonstop",
        "price": "$420",
        "original_price": "$520",
        "savings": "$100",
    },
]

MOCK_HIDDEN_CITY_FLIGHTS = [
    {
        "airline": "United",
        "departure_time": "07:30",
        "arrival_time": "16:00",
        "duration": "8h 30m",
        "stops": "1 stop",
        "price": "$320",
        "layovers": ["MCO"],  # MCO is our target!
    },
    {
        "airline": "Delta",
        "departure_time": "11:00",
        "arrival_time": "19:30",
        "duration": "8h 30m",
        "stops": "1 stop",
        "price": "$350",
        "layovers": ["ATL"],  # Not our target
    },
]


async def mock_google_flights(*args, **kwargs):
    """Mock Google Flights scraper."""
    await asyncio.sleep(0.1)  # Simulate network delay
    return MOCK_GOOGLE_FLIGHTS


async def mock_skiplagged_flights(*args, **kwargs):
    """Mock Skiplagged scraper."""
    await asyncio.sleep(0.1)
    return MOCK_SKIPLAGGED_FLIGHTS


async def mock_google_flights_for_hidden_city(origin, destination, *args, **kwargs):
    """Mock Google Flights for hidden city searches."""
    await asyncio.sleep(0.1)
    # Return flights with MCO layover for some destinations
    if destination in ["JFK", "BOS", "LGA"]:
        return MOCK_HIDDEN_CITY_FLIGHTS
    return []


def mock_get_target_routes(destination, origin=None):
    """Mock route database."""
    if origin == "GRU" and destination == "MCO":
        return (["JFK", "BOS", "LGA"], True)  # Pair-specific
    return (["JFK", "BOS"], False)  # Default


async def run_mock_test():
    """Run the parallel search with mocked scrapers."""

    print("\n" + "=" * 70)
    print("MOCK TEST: Parallel Flight Search Logic")
    print("=" * 70)

    # Import after path setup
    with patch('src.parallel_search.search_google_flights', mock_google_flights), \
         patch('src.parallel_search.search_skiplagged_flights', mock_skiplagged_flights), \
         patch('src.parallel_search.get_target_routes', mock_get_target_routes):

        # Re-import to pick up mocks
        from src.parallel_search import ParallelFlightSearch

        # For hidden city, we need to patch at the method level
        search = ParallelFlightSearch(max_concurrent_hidden_city=2)

        # Patch the hidden city google flights calls
        original_search_hidden_city = search._search_hidden_city

        async def patched_search_hidden_city(origin, destination, departure_date):
            """Patched hidden city search using mock."""
            import asyncio
            from src.models import normalize_orchestrator_flight
            from src.utils.layover_detection import get_city_variants_set

            start_time = asyncio.get_event_loop().time()

            # Get mock routes
            target_routes, _ = mock_get_target_routes(destination, origin)

            results = []
            target_variants = get_city_variants_set(destination)

            for final_dest in target_routes:
                raw_flights = await mock_google_flights_for_hidden_city(origin, final_dest)

                for flight in raw_flights:
                    layovers = flight.get('layovers', [])

                    # Check if destination is a layover
                    confirmed = any(l.upper() in target_variants for l in layovers)

                    if confirmed or not layovers:
                        enriched = {
                            **flight,
                            'final_destination': final_dest,
                            'hidden_city_target': destination,
                            'search_route': f"{origin} → {final_dest}",
                            'deal_type': 'hidden_city' if confirmed else 'potential_hidden_city',
                            'confirmed_layover': confirmed,
                        }
                        normalized = normalize_orchestrator_flight(enriched, origin, destination)
                        results.append(normalized)

            search_time = asyncio.get_event_loop().time() - start_time
            return results, search_time

        search._search_hidden_city = patched_search_hidden_city

        print("\nRunning parallel search: GRU → MCO on 2026-03-20")
        print("-" * 70)

        results = await search.search_all(
            origin="GRU",
            destination="MCO",
            departure_date="2026-03-20",
        )

        # Verify results
        print("\n✓ Search completed successfully!")
        print(f"  Total time: {results.total_search_time_seconds:.2f}s")
        print(f"  Total flights: {results.total_flights_found}")

        print("\n--- Source Results ---")
        for source, sr in results.source_results.items():
            print(f"  {source}: {sr.status.value} - {len(sr.flights)} flights")

        print("\n--- Best Deals ---")
        if results.best_direct:
            print(f"  Best Direct: {results.best_direct.price} ({results.best_direct.airline})")
        if results.best_skiplagged:
            print(f"  Best Skiplagged: {results.best_skiplagged.price} ({results.best_skiplagged.airline})")
        if results.best_hidden_city:
            hc = results.best_hidden_city
            print(f"  Best Hidden City: {hc.price} ({hc.airline})")
            print(f"    → Book: {hc.search_route}, Exit at: {hc.hidden_city_target}")
        if results.best_overall:
            print(f"\n  BEST OVERALL: {results.best_overall.price} from {results.best_overall.source.value}")

        print("\n--- All Flights (sorted by price) ---")
        for i, f in enumerate(results.all_flights, 1):
            source_tag = f"[{f.source.value}]"
            hc_tag = f" HC:{f.hidden_city_target}" if f.deal_type.value == "hidden_city" else ""
            print(f"  {i}. {f.price} - {f.airline} {source_tag}{hc_tag}")

        # Validation checks
        print("\n" + "=" * 70)
        print("VALIDATION CHECKS")
        print("=" * 70)

        checks = [
            ("Sources succeeded count", len(results.sources_succeeded) == 3),
            ("Google Flights returned flights", len(results.source_results.get("google_flights", {}).flights or []) > 0),
            ("Skiplagged returned flights", len(results.source_results.get("skiplagged", {}).flights or []) > 0),
            ("Hidden City found deals", results.best_hidden_city is not None),
            ("Flights sorted by price", all(
                results.all_flights[i].price_numeric <= results.all_flights[i+1].price_numeric
                for i in range(len(results.all_flights)-1)
            ) if len(results.all_flights) > 1 else True),
            ("Best overall is cheapest",
             results.best_overall == results.all_flights[0] if results.all_flights else True),
        ]

        all_passed = True
        for name, passed in checks:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}: {name}")
            if not passed:
                all_passed = False

        print("\n" + "=" * 70)
        if all_passed:
            print("ALL TESTS PASSED! Parallel search logic is working correctly.")
        else:
            print("SOME TESTS FAILED. Check the implementation.")
        print("=" * 70)

        return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_mock_test())
    sys.exit(0 if success else 1)
