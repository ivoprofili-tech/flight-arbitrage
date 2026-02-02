#!/usr/bin/env python3
"""
Test script for the parallel flight search engine.

Usage:
    python scripts/test_parallel_search.py
    python scripts/test_parallel_search.py GRU MCO 2026-03-20
    python scripts/test_parallel_search.py --sources google_flights,skiplagged
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parallel_search import search_flights, ParallelFlightSearch


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_test(
    origin: str,
    destination: str,
    departure_date: str,
    sources: list[str] | None = None,
    headless: bool = True,
    max_concurrent: int = 2,
):
    """Run a test search and display results."""

    print("\n" + "=" * 70)
    print(f"PARALLEL FLIGHT SEARCH TEST")
    print("=" * 70)
    print(f"Route: {origin} → {destination}")
    print(f"Date: {departure_date}")
    print(f"Sources: {sources or ['all']}")
    print(f"Headless: {headless}")
    print("=" * 70 + "\n")

    try:
        results = await search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            sources=sources,
            max_concurrent=max_concurrent,
            headless=headless,
        )

        # Display summary
        print("\n" + "=" * 70)
        print("SEARCH RESULTS SUMMARY")
        print("=" * 70)
        print(f"Total search time: {results.total_search_time_seconds:.2f}s")
        print(f"Total flights found: {results.total_flights_found}")
        print(f"Sources succeeded: {results.sources_succeeded}")
        print(f"Sources failed: {results.sources_failed}")

        # Source breakdown
        print("\n--- Source Breakdown ---")
        for source_name, source_result in results.source_results.items():
            status = source_result.status.value
            count = len(source_result.flights)
            time = source_result.search_time_seconds
            error = source_result.error_message or ""
            print(f"  {source_name}: {status} - {count} flights in {time:.2f}s {error}")

        # Best deals
        print("\n--- Best Deals ---")
        if results.best_direct:
            print(f"  Best Direct: {results.best_direct.price} - {results.best_direct.airline}")
        else:
            print("  Best Direct: None found")

        if results.best_skiplagged:
            print(f"  Best Skiplagged: {results.best_skiplagged.price} - {results.best_skiplagged.airline}")
        else:
            print("  Best Skiplagged: None found")

        if results.best_hidden_city:
            hc = results.best_hidden_city
            print(f"  Best Hidden City: {hc.price} - {hc.airline}")
            print(f"    Book route: {hc.search_route}")
            print(f"    Exit at: {hc.hidden_city_target}")
        else:
            print("  Best Hidden City: None found")

        if results.best_overall:
            print(f"\n  BEST OVERALL: {results.best_overall.price} - {results.best_overall.airline} ({results.best_overall.source.value})")

        # Top 10 flights
        print("\n--- Top 10 Cheapest Flights ---")
        for i, flight in enumerate(results.all_flights[:10], 1):
            deal_info = ""
            if flight.deal_type.value == "hidden_city":
                deal_info = f" [HC: book {flight.final_destination}, exit {flight.hidden_city_target}]"
            elif flight.source.value == "skiplagged":
                deal_info = " [Skiplagged]"

            stops = flight.stops if flight.stops != "Nonstop" else "Direct"
            print(f"  {i}. {flight.price} - {flight.airline} - {stops}{deal_info}")

        # Option to save full results
        print("\n--- Full Results ---")
        output_file = f"search_results_{origin}_{destination}_{departure_date}.json"
        with open(output_file, 'w') as f:
            json.dump(results.to_dict(), f, indent=2)
        print(f"Full results saved to: {output_file}")

        return results

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Test parallel flight search")
    parser.add_argument("origin", nargs="?", default="GRU", help="Origin airport code")
    parser.add_argument("destination", nargs="?", default="MCO", help="Destination airport code")
    parser.add_argument("date", nargs="?", default="2026-03-20", help="Departure date (YYYY-MM-DD)")
    parser.add_argument("--sources", type=str, help="Comma-separated sources: google_flights,skiplagged,hidden_city")
    parser.add_argument("--no-headless", action="store_true", help="Show browser windows")
    parser.add_argument("--max-concurrent", type=int, default=2, help="Max concurrent hidden city searches")

    args = parser.parse_args()

    sources = None
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",")]

    asyncio.run(run_test(
        origin=args.origin,
        destination=args.destination,
        departure_date=args.date,
        sources=sources,
        headless=not args.no_headless,
        max_concurrent=args.max_concurrent,
    ))


if __name__ == "__main__":
    main()
