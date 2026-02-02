#!/usr/bin/env python3
"""
Real-world parallel flight search script.

Run actual searches against Google Flights, Skiplagged, and hidden city routes.

Usage:
    # Default: GRU → MCO, 30 days from now
    python scripts/run_parallel_search.py

    # Custom route and date
    python scripts/run_parallel_search.py GRU MCO 2026-04-15

    # Single source only
    python scripts/run_parallel_search.py --sources google_flights
    python scripts/run_parallel_search.py --sources skiplagged
    python scripts/run_parallel_search.py --sources hidden_city

    # Multiple sources
    python scripts/run_parallel_search.py --sources google_flights,skiplagged

    # Show browser (not headless)
    python scripts/run_parallel_search.py --visible

    # Limit hidden city concurrent searches
    python scripts/run_parallel_search.py --max-concurrent 1

    # Quick test with limited hidden city routes
    python scripts/run_parallel_search.py --quick
"""

import asyncio
import argparse
import json
import logging
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

# Suppress asyncio event loop closed warnings (harmless cleanup noise)
warnings.filterwarnings("ignore", message=".*Event loop is closed.*")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parallel_search import search_flights, ParallelFlightSearch
from src.data.route_database import get_target_routes, get_destination_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Reduce noise from other loggers
logging.getLogger('playwright').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)


def print_header(title: str, char: str = "="):
    """Print a formatted header."""
    width = 70
    print(f"\n{char * width}")
    print(f" {title}")
    print(f"{char * width}")


def print_flight(i: int, flight, show_details: bool = True):
    """Print a single flight result."""
    source_tags = {
        "google_flights": "GF",
        "skiplagged": "SL",
        "hidden_city": "HC",
    }

    source = source_tags.get(flight.source.value, flight.source.value)
    deal_type = flight.deal_type.value

    # Build tags
    tags = [f"[{source}]"]
    if deal_type == "hidden_city":
        tags.append(f"EXIT@{flight.hidden_city_target}")
    elif flight.savings:
        tags.append(f"SAVE {flight.savings}")

    stops = flight.stops if flight.stops else "?"
    if stops == "Nonstop":
        stops = "Direct"

    tag_str = " ".join(tags)

    print(f"  {i:2}. {flight.price:>8} | {flight.airline:<15} | {stops:<10} | {tag_str}")

    if show_details and deal_type == "hidden_city":
        print(f"      └── Book: {flight.search_route} → Exit at layover: {flight.hidden_city_target}")


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"


async def run_search(
    origin: str,
    destination: str,
    departure_date: str,
    sources: list[str] | None = None,
    headless: bool = True,
    max_concurrent: int = 2,
    quick: bool = False,
    save_results: bool = True,
):
    """Run a real parallel flight search."""

    print_header(f"FLIGHT SEARCH: {origin} → {destination}")
    print(f" Date: {departure_date}")
    print(f" Sources: {', '.join(sources) if sources else 'all'}")
    print(f" Mode: {'headless' if headless else 'visible browser'}")
    print(f" Concurrency: {max_concurrent} parallel searches")

    # Show route info and calculate expected timeout
    targets, is_pair_specific = get_target_routes(destination, origin)
    if sources is None or "hidden_city" in sources:
        route_type = "pair-specific" if is_pair_specific else "default"
        target_count = len(targets) if not quick else min(3, len(targets))
        print(f" Hidden city routes: {target_count} targets ({route_type})")
        if quick and len(targets) > 3:
            print(f"   → Quick mode: limited to first 3 routes")

        # Calculate and show expected timeout
        batches = (target_count + max_concurrent - 1) // max_concurrent
        base_timeout = 180  # 3 min for direct searches
        hc_timeout = batches * 60  # ~60s per batch
        total_timeout = base_timeout + hc_timeout
        print(f" Expected timeout: {format_duration(total_timeout)} ({batches} batches × ~60s + base)")

    print_header("SEARCHING...", "-")
    start_time = datetime.now()

    try:
        # For quick mode, limit the routes
        if quick:
            # Create a custom search with limited routes (3 routes, shorter timeout)
            num_routes = 3  # Quick mode uses 3 routes max
            search = ParallelFlightSearch(
                max_concurrent_hidden_city=max_concurrent,
                headless=headless,
                num_hidden_city_routes=num_routes,
            )

            # Monkey-patch to limit routes
            original_search_hidden_city = search._search_hidden_city

            async def limited_hidden_city(origin, destination, departure_date):
                # Temporarily limit routes
                import src.data.route_database as rdb
                original_pair_routes = rdb.PAIR_ROUTES.copy()
                original_route_db = {k: v.copy() for k, v in rdb.ROUTE_DATABASE.items()}

                # Limit to first 3 routes
                for key in rdb.PAIR_ROUTES:
                    rdb.PAIR_ROUTES[key] = rdb.PAIR_ROUTES[key][:3]
                for key in rdb.ROUTE_DATABASE:
                    if "targets" in rdb.ROUTE_DATABASE[key]:
                        rdb.ROUTE_DATABASE[key]["targets"] = rdb.ROUTE_DATABASE[key]["targets"][:3]

                try:
                    result = await original_search_hidden_city(origin, destination, departure_date)
                finally:
                    # Restore
                    rdb.PAIR_ROUTES.update(original_pair_routes)
                    for key in original_route_db:
                        rdb.ROUTE_DATABASE[key] = original_route_db[key]

                return result

            search._search_hidden_city = limited_hidden_city

            results = await search.search_all(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                sources=sources,
            )
        else:
            # Full search - timeout auto-calculated based on route count
            results = await search_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                sources=sources,
                max_concurrent=max_concurrent,
                headless=headless,
            )

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        return None

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    # Results summary
    print_header("RESULTS SUMMARY")
    print(f" Total search time: {format_duration(total_duration)}")
    print(f" Flights found: {results.total_flights_found}")
    print(f" Sources OK: {', '.join(results.sources_succeeded) or 'none'}")
    if results.sources_failed:
        print(f" Sources FAILED: {', '.join(results.sources_failed)}")

    # Source breakdown
    print_header("SOURCE BREAKDOWN", "-")
    for source_name, sr in results.source_results.items():
        status_icon = "✓" if sr.status.value == "success" else "✗"
        time_str = format_duration(sr.search_time_seconds)
        count = len(sr.flights)

        print(f" {status_icon} {source_name}: {count} flights in {time_str}")
        if sr.error_message:
            error_preview = sr.error_message[:60] + "..." if len(sr.error_message) > 60 else sr.error_message
            print(f"    Error: {error_preview}")

    # Best deals
    print_header("BEST DEALS", "-")

    if results.best_direct:
        bd = results.best_direct
        print(f" Best Direct:      {bd.price:>8} | {bd.airline} | {bd.stops}")
    else:
        print(f" Best Direct:      None found")

    if results.best_skiplagged:
        bs = results.best_skiplagged
        savings = f" (save {bs.savings})" if bs.savings else ""
        print(f" Best Skiplagged:  {bs.price:>8} | {bs.airline}{savings}")
    else:
        print(f" Best Skiplagged:  None found")

    if results.best_hidden_city:
        bh = results.best_hidden_city
        print(f" Best Hidden City: {bh.price:>8} | {bh.airline}")
        print(f"    └── Book {bh.search_route}, exit at {bh.hidden_city_target}")
    else:
        print(f" Best Hidden City: None found")

    # Overall best
    if results.best_overall:
        bo = results.best_overall
        print_header("BEST OVERALL DEAL")
        print(f" Price: {bo.price}")
        print(f" Airline: {bo.airline}")
        print(f" Source: {bo.source.value}")
        print(f" Stops: {bo.stops}")
        if bo.deal_type.value == "hidden_city":
            print(f" Strategy: Book {bo.search_route}")
            print(f" Action: Exit at {bo.hidden_city_target} layover")

        # Calculate savings vs direct
        if results.best_direct and results.best_direct != results.best_overall:
            direct_price = results.best_direct.price_numeric
            best_price = results.best_overall.price_numeric
            if direct_price > best_price:
                savings = direct_price - best_price
                pct = (savings / direct_price) * 100
                print(f" Savings vs direct: ${savings} ({pct:.0f}%)")

    # All flights list
    if results.all_flights:
        print_header(f"ALL FLIGHTS ({len(results.all_flights)} total)", "-")
        for i, flight in enumerate(results.all_flights[:20], 1):
            print_flight(i, flight, show_details=True)

        if len(results.all_flights) > 20:
            print(f"\n  ... and {len(results.all_flights) - 20} more flights")

    # Save results
    if save_results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results_{origin}_{destination}_{departure_date}_{timestamp}.json"
        output_dir = Path("search_results")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / filename

        with open(output_path, 'w') as f:
            json.dump(results.to_dict(), f, indent=2)

        print_header("OUTPUT", "-")
        print(f" Results saved to: {output_path}")

    print_header("SEARCH COMPLETE")

    return results


def get_default_date() -> str:
    """Get a default search date (30 days from now)."""
    future = datetime.now() + timedelta(days=30)
    return future.strftime("%Y-%m-%d")


def push_results_to_github():
    """Push debug files and results to GitHub, then clean up locally."""
    import subprocess
    import time

    branch = "claude/parallel-scraper-consolidation-D2RiE"

    print_header("PUSHING RESULTS TO GITHUB")

    # Add all debug/result files
    subprocess.run(
        "git add search_results/ debug_*.txt debug_*.png videos/*.webm 2>/dev/null",
        shell=True, capture_output=True
    )

    # Check if there's anything to commit
    result = subprocess.run("git diff --cached --quiet", shell=True)
    if result.returncode == 0:
        print(" No new files to commit")
    else:
        # Commit
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        subprocess.run(
            f'git commit -m "Test results {timestamp}"',
            shell=True, capture_output=True
        )
        print(" ✓ Committed new results")

    # Fetch, rebase, and push with retry
    max_retries = 4
    delays = [2, 4, 8, 16]

    for attempt in range(max_retries):
        # First fetch
        print(" Fetching latest changes...")
        fetch_result = subprocess.run(
            f"git fetch origin {branch}",
            shell=True, capture_output=True
        )

        if fetch_result.returncode != 0:
            print(f" ✗ Fetch failed: {fetch_result.stderr.decode()}")
            if attempt < max_retries - 1:
                print(f" Retrying in {delays[attempt]}s...")
                time.sleep(delays[attempt])
                continue
            return

        # Rebase onto fetched changes
        print(" Rebasing onto latest...")
        rebase_result = subprocess.run(
            f"git rebase origin/{branch}",
            shell=True, capture_output=True
        )

        if rebase_result.returncode != 0:
            print(f" ✗ Rebase conflict - aborting rebase")
            subprocess.run("git rebase --abort", shell=True, capture_output=True)
            # Try to just push anyway - maybe we're ahead
            pass

        # Push
        print(" Pushing to GitHub...")
        result = subprocess.run(
            f"git push origin {branch}",
            shell=True, capture_output=True
        )

        if result.returncode == 0:
            print(" ✓ Pushed successfully")
            break
        else:
            error_msg = result.stderr.decode()
            if "fetch first" in error_msg or "rejected" in error_msg:
                print(f" ✗ Push rejected (remote has changes)")
                if attempt < max_retries - 1:
                    print(f" Retrying in {delays[attempt]}s...")
                    time.sleep(delays[attempt])
                    continue
            print(f" ✗ Push failed: {error_msg}")
            return
    else:
        print(" ✗ Failed after all retries")
        return

    # Clean up local files
    print(" Cleaning up local debug files...")
    subprocess.run("rm -f debug_*.png debug_*.txt 2>/dev/null", shell=True)
    subprocess.run("rm -f search_results/*.json 2>/dev/null", shell=True)
    subprocess.run("rm -f videos/*.webm 2>/dev/null", shell=True)
    print(" ✓ Local files cleaned")

    print_header("READY FOR NEXT TEST")


def main():
    parser = argparse.ArgumentParser(
        description="Run parallel flight search across multiple sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_parallel_search.py                          # Default GRU→MCO
  python scripts/run_parallel_search.py GRU MIA 2026-04-15       # Custom route/date
  python scripts/run_parallel_search.py --sources google_flights # Single source
  python scripts/run_parallel_search.py --visible                # Show browser
  python scripts/run_parallel_search.py --quick                  # Fast test (3 HC routes)
        """
    )

    parser.add_argument(
        "origin",
        nargs="?",
        default="GRU",
        help="Origin airport code (default: GRU)"
    )
    parser.add_argument(
        "destination",
        nargs="?",
        default="MCO",
        help="Destination airport code (default: MCO)"
    )
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Departure date YYYY-MM-DD (default: 30 days from now)"
    )
    parser.add_argument(
        "--sources", "-s",
        type=str,
        help="Comma-separated sources: google_flights,skiplagged,hidden_city"
    )
    parser.add_argument(
        "--visible", "-v",
        action="store_true",
        help="Show browser windows (not headless)"
    )
    parser.add_argument(
        "--max-concurrent", "-c",
        type=int,
        default=2,
        help="Max concurrent hidden city searches (default: 2)"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick mode: limit to 3 hidden city routes"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file"
    )
    parser.add_argument(
        "--push", "-p",
        action="store_true",
        help="Push results to GitHub after search completes"
    )

    args = parser.parse_args()

    # Parse sources
    sources = None
    if args.sources:
        sources = [s.strip().lower() for s in args.sources.split(",")]
        valid = {"google_flights", "skiplagged", "hidden_city"}
        for s in sources:
            if s not in valid:
                print(f"Error: Invalid source '{s}'. Valid options: {valid}")
                sys.exit(1)

    # Get date
    departure_date = args.date or get_default_date()

    # Run search with proper cleanup handling
    try:
        asyncio.run(run_search(
            origin=args.origin.upper(),
            destination=args.destination.upper(),
            departure_date=departure_date,
            sources=sources,
            headless=not args.visible,
            max_concurrent=args.max_concurrent,
            quick=args.quick,
            save_results=not args.no_save,
        ))
    except RuntimeError as e:
        # Ignore "Event loop is closed" errors during cleanup
        if "Event loop is closed" not in str(e):
            raise
    except KeyboardInterrupt:
        print("\n Search cancelled by user")
        sys.exit(1)

    # Push results if requested
    if args.push:
        push_results_to_github()


if __name__ == "__main__":
    main()
