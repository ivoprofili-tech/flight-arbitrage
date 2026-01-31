#!/usr/bin/env python3
"""
Skiplagging Search Script
=========================

Search for hidden-city fare opportunities by finding flights where your
true destination appears as a layover on a cheaper route.

Usage:
    python scripts/test_skiplag.py <origin> <destination> <date> [options]

Examples:
    python scripts/test_skiplag.py JFK DEN 2026-03-15
    python scripts/test_skiplag.py JFK DEN 2026-03-15 --show-browser
    python scripts/test_skiplag.py JFK DEN 2026-03-15 --targets LAX,SFO,SEA
    python scripts/test_skiplag.py --list-destinations

Hidden-City Concept:
    You want to fly JFK -> DEN (Denver)
    We search JFK -> LAX, JFK -> SFO (cities BEYOND Denver)
    If a JFK -> LAX flight stops in DEN, that's a hidden-city opportunity!
    You book JFK -> LAX but get off at the DEN layover.
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import execute_targeted_skiplag_search
from src.data.route_database import (
    get_target_routes,
    get_destination_info,
    list_supported_destinations,
    ROUTE_DATABASE,
)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Search for hidden-city (skiplagging) flight deals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s JFK DEN 2026-03-15           Search JFK->DEN using default routes
  %(prog)s JFK PHX 2026-03-15 --show-browser   Watch the browser scrape
  %(prog)s JFK ATL 2026-03-15 --targets MIA,FLL,TPA   Specify routes manually
  %(prog)s --list-destinations          Show all supported destinations
        """
    )

    # Positional arguments (optional if using --list-destinations)
    parser.add_argument(
        "origin",
        nargs="?",
        help="Origin airport code (e.g., JFK, LAX, ORD)"
    )
    parser.add_argument(
        "destination",
        nargs="?",
        help="True destination - will look for this as a LAYOVER (e.g., DEN, PHX)"
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="Departure date in YYYY-MM-DD format (default: 2 weeks from now)"
    )

    # Optional arguments
    parser.add_argument(
        "--targets", "-t",
        help="Comma-separated list of target routes (cities beyond destination). "
             "If not provided, uses database defaults."
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=5,
        help="Max number of target routes to search (default: 5)"
    )
    parser.add_argument(
        "--show-browser", "-s",
        action="store_true",
        help="Show browser window while scraping (headless=False)"
    )
    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=1,
        help="Number of concurrent searches (default: 1)"
    )
    parser.add_argument(
        "--list-destinations", "-L",
        action="store_true",
        help="List all supported destinations in the database"
    )
    parser.add_argument(
        "--info", "-i",
        metavar="CODE",
        help="Show detailed info for a specific destination"
    )

    return parser.parse_args()


def show_destinations():
    """Display all supported destinations."""
    print("\n" + "=" * 60)
    print("SUPPORTED DESTINATIONS")
    print("=" * 60)
    print("\nThese destinations have pre-configured 'beyond' routes:\n")

    destinations = list_supported_destinations()

    for code in destinations:
        info = ROUTE_DATABASE[code]
        targets = info["targets"][:4]
        hub_info = f" [{', '.join(info['hub_for'])}]" if info['hub_for'] else ""
        print(f"  {code}{hub_info}")
        print(f"      → Search routes: {', '.join(targets)}...")
        print()

    print(f"Total: {len(destinations)} destinations")
    print("\nUsage: python scripts/test_skiplag.py JFK <destination> <date>")


def show_destination_info(code: str):
    """Display detailed info for a destination."""
    info = get_destination_info(code)

    if not info:
        print(f"\n'{code}' not found in database.")
        print("\nUse --list-destinations to see available options.")
        print("Or specify routes manually with --targets LAX,SFO,SEA")
        return

    print("\n" + "=" * 60)
    print(f"DESTINATION: {code.upper()}")
    print("=" * 60)
    print(f"\nHub airlines: {', '.join(info.get('hub_for', [])) or 'None'}")
    print(f"Notes: {info.get('notes', 'N/A')}")
    print(f"\nSuggested 'beyond' routes (search these for {code} layovers):")
    for i, target in enumerate(info.get("targets", []), 1):
        print(f"  {i}. {target}")
    print(f"\nExample command:")
    print(f"  python scripts/test_skiplag.py JFK {code} 2026-03-15")


async def run_search(args):
    """Execute the skiplag search."""
    origin = args.origin.upper()
    destination = args.destination.upper()

    # Handle date
    if args.date:
        date = args.date
    else:
        # Default to 2 weeks from now
        departure = datetime.now() + timedelta(days=14)
        date = departure.strftime('%Y-%m-%d')

    # Get target routes
    if args.targets:
        target_routes = [t.strip().upper() for t in args.targets.split(",")]
    else:
        target_routes = get_target_routes(destination, limit=args.limit)
        if not target_routes:
            print(f"\nNo default routes for '{destination}' in database.")
            print("\nOptions:")
            print("  1. Specify routes manually: --targets LAX,SFO,SEA")
            print("  2. Use --list-destinations to see supported destinations")
            print("\nHint: Target routes should be cities BEYOND your destination")
            print(f"      that might have {destination} as a layover.")
            return []

    # Display search configuration
    print("\n" + "=" * 60)
    print("SKIPLAGGING SEARCH")
    print("=" * 60)
    print(f"\n  Origin:      {origin}")
    print(f"  Destination: {destination} (looking for this as a LAYOVER)")
    print(f"  Date:        {date}")
    print(f"  Routes:      {origin} → {', '.join(target_routes)}")
    print(f"  Browser:     {'Visible' if args.show_browser else 'Headless'}")
    print(f"  Concurrent:  {args.concurrent}")

    info = get_destination_info(destination)
    if info:
        print(f"\n  {destination} Info: {info.get('notes', '')}")

    print("\n" + "-" * 60)
    input("\nPress Enter to start search (Ctrl+C to cancel)...")
    print()

    # Run the search
    results = await execute_targeted_skiplag_search(
        origin_A=origin,
        destination_B=destination,
        date=date,
        target_routes=target_routes,
        headless=not args.show_browser,
        max_concurrent=args.concurrent
    )

    # Display results
    print_results(results, destination)

    return results


def print_results(results: list, destination: str):
    """Pretty-print the search results."""
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    if not results:
        print(f"\nNo flights found with {destination} as a layover.")
        print("\nTips:")
        print("  - Try different target routes (cities further from origin)")
        print("  - Try a different date")
        print("  - Some routes may not stop at your destination")
        return

    # Categorize results
    confirmed = [r for r in results if r.get('deal_type') == 'hidden_city']
    not_target = [r for r in results if r.get('deal_type') == 'not_target_layover']
    potential = [r for r in results if r.get('deal_type') == 'potential_hidden_city']

    print(f"\n  Total flights with stops: {len(results)}")
    print(f"  Confirmed {destination} layovers: {len(confirmed)}")
    print(f"  Other layovers: {len(not_target)}")
    print(f"  Unknown (check manually): {len(potential)}")

    if confirmed:
        print("\n" + "-" * 40)
        print(f"HIDDEN-CITY DEALS (layover at {destination})")
        print("-" * 40)
        for i, flight in enumerate(confirmed, 1):
            print(f"\n  [{i}] {flight.get('price', 'N/A')}")
            print(f"      Route: {flight.get('search_route', 'N/A')}")
            print(f"      Layovers: {flight.get('layovers', [])}")
            print(f"      Airline: {flight.get('airline', 'N/A')}")
            print(f"      Times: {flight.get('departure_time', '')} → {flight.get('arrival_time', '')}")
            print(f"      Duration: {flight.get('duration', 'N/A')}")

    if not_target:
        print("\n" + "-" * 40)
        print(f"OTHER CONNECTING FLIGHTS (not {destination})")
        print("-" * 40)
        # Show top 5
        for i, flight in enumerate(not_target[:5], 1):
            layovers = flight.get('layovers', [])
            print(f"  [{i}] {flight.get('price', 'N/A')} - {flight.get('search_route')} via {layovers}")

        if len(not_target) > 5:
            print(f"  ... and {len(not_target) - 5} more")

    if potential:
        print("\n" + "-" * 40)
        print("POTENTIAL DEALS (verify layover manually)")
        print("-" * 40)
        for i, flight in enumerate(potential[:3], 1):
            print(f"  [{i}] {flight.get('price', 'N/A')} - {flight.get('search_route')}")
            print(f"      Stops: {flight.get('stops', 'N/A')}")


async def main():
    """Main entry point."""
    args = parse_args()

    # Handle info/list commands
    if args.list_destinations:
        show_destinations()
        return

    if args.info:
        show_destination_info(args.info)
        return

    # Validate required arguments for search
    if not args.origin or not args.destination:
        print("\nError: origin and destination are required for search")
        print("\nUsage: python scripts/test_skiplag.py <origin> <destination> [date]")
        print("       python scripts/test_skiplag.py --list-destinations")
        print("       python scripts/test_skiplag.py --info DEN")
        print("\nExamples:")
        print("  python scripts/test_skiplag.py JFK DEN 2026-03-15")
        print("  python scripts/test_skiplag.py JFK PHX 2026-03-15 --show-browser")
        return

    try:
        await run_search(args)
    except KeyboardInterrupt:
        print("\n\nSearch cancelled.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
