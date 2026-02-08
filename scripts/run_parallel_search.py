#!/usr/bin/env python3
"""
Real-world parallel flight search script.

Run actual searches against Google Flights, Skiplagged, and hidden city routes.
Supports HYBRID geo-location arbitrage to compare prices across different countries.

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

    # HYBRID GEO ARBITRAGE (recommended):
    # Phase 1: Full parallel search to discover hidden city deals
    # Phase 2: Geo-compare direct route + discovered hidden city routes
    python scripts/run_parallel_search.py --geo                    # All 5 locations
    python scripts/run_parallel_search.py --geo --locations BR,US  # Specific locations
    python scripts/run_parallel_search.py --geo --quick            # Quick mode (3 HC routes)
    python scripts/run_parallel_search.py --geo --push             # Push results to GitHub

    # Geo arbitrage (uses SerpApi gl parameter -- no proxy needed for Google Flights):
    # Just set SERPAPI_KEY in .env and run:
    python scripts/run_parallel_search.py --geo
"""

import asyncio
import argparse
import json
import logging
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

# Suppress asyncio event loop closed warnings (harmless cleanup noise)
warnings.filterwarnings("ignore", message=".*Event loop is closed.*")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if it exists (for proxy credentials)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

# NOTE: Heavy imports (src.parallel_search, src.geo.*) are done lazily
# inside run_search() and run_geo_search() so that sync_with_remote()
# can update files on disk BEFORE the modules are loaded into memory.
from src.geo.proxy_config import LOCATIONS, init_proxy_provider

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

# Git branch for syncing code and results
GIT_BRANCH = "claude/test-parallel-search-wFmxs"


def sync_with_remote():
    """Sync local repo with remote before running search. Fixes pull conflicts."""
    import subprocess

    print(" Syncing with remote...")

    # Clean up any local debug files first
    subprocess.run("rm -f debug_*.png debug_*.txt 2>/dev/null", shell=True)
    subprocess.run("rm -f search_results/*.json 2>/dev/null", shell=True)
    subprocess.run("rm -f videos/*.webm 2>/dev/null", shell=True)

    # Fetch latest from remote
    fetch_result = subprocess.run(
        f"git fetch origin {GIT_BRANCH}",
        shell=True, capture_output=True
    )

    if fetch_result.returncode != 0:
        print(f" ⚠ Fetch failed (offline?): {fetch_result.stderr.decode()[:100]}")
        return False

    # Ensure we're on a local branch with the correct name.
    # Without this, git reset --hard leaves us on a different branch
    # (or detached HEAD), and later `git push origin {GIT_BRANCH}` fails
    # with "src refspec does not match any".
    subprocess.run(
        f"git checkout -B {GIT_BRANCH} origin/{GIT_BRANCH}",
        shell=True, capture_output=True
    )

    print(" ✓ Synced with remote")
    return True


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
    from src.parallel_search import search_flights, ParallelFlightSearch
    from src.data.route_database import get_target_routes, get_destination_info

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


async def run_geo_search(
    origin: str,
    destination: str,
    departure_date: str,
    locations: list[str],
    headless: bool = True,
    max_concurrent: int = 3,
    save_results: bool = True,
    quick: bool = False,
):
    """
    Run HYBRID geo arbitrage search.

    Phase 1: Run full parallel search (GF + Skiplagged + Hidden City)
    Phase 2: Run geo arbitrage on direct route + discovered hidden city routes

    This is more efficient than running full searches from each location.
    """
    from src.geo.geo_search import run_hybrid_geo_search, MultiRouteGeoResult

    print_header(f"HYBRID GEO ARBITRAGE: {origin} → {destination}")
    print(f" Date: {departure_date}")
    print(f" Locations: {', '.join(locations)}")
    print(f" Mode: {'headless' if headless else 'visible browser'}")
    print(f" Geo concurrency: {max_concurrent} parallel location searches")
    print()
    print(" Strategy:")
    print("   Phase 1: Run full parallel search to discover hidden city deals")
    print("   Phase 2: Geo-search direct route + discovered hidden city routes")

    print_header("PHASE 1: DISCOVERING HIDDEN CITY ROUTES...", "-")

    try:
        results = await run_hybrid_geo_search(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            locations=locations,
            max_concurrent=max_concurrent,
            headless=headless,
            initial_search_quick=quick,
        )

    except Exception as e:
        logger.exception(f"Hybrid geo search failed: {e}")
        return None

    # Phase 1 summary
    print_header("PHASE 1 RESULTS", "-")
    print(f" Initial search time: {format_duration(results.initial_search_time_seconds)}")
    if results.direct_route_best_price:
        print(f" Direct route best price: ${results.direct_route_best_price:.2f}")
    print(f" Hidden city routes found: {len(results.hidden_city_routes_found)}")

    if results.hidden_city_routes_found:
        print()
        for route in results.hidden_city_routes_found:
            price_str = f"${route.original_price:.2f}" if route.original_price else "N/A"
            print(f"   • {route.origin}→{route.destination} (exit@{route.hidden_city_exit}) - {price_str}")

    # Phase 2 summary
    print_header("PHASE 2: GEO ARBITRAGE RESULTS", "-")
    print(f" Total search time: {format_duration(results.total_search_time_seconds)}")
    print(f" Routes geo-searched: {results.total_routes_searched}")

    # Direct route geo results
    if results.best_direct_deal:
        dd = results.best_direct_deal
        print_header("DIRECT ROUTE GEO COMPARISON", "-")
        print(f" Route: {dd['route']}")
        print(f" Best location: {dd['best_location']} ({LOCATIONS.get(dd['best_location'], type('obj', (object,), {'name': dd['best_location']})()).name})")
        print(f" Best price: ${dd['best_price_usd']:.2f} ({dd['original_price']})")
        print(f" Airline: {dd['airline']}")
        if dd.get('stops'):
            layover_str = f" via {', '.join(dd['layovers'])}" if dd.get('layovers') else ""
            print(f" Flight type: {dd['stops']}{layover_str}")

        if dd['potential_savings_usd'] > 0:
            print(f" Geo savings: ${dd['potential_savings_usd']:.2f} ({dd['potential_savings_pct']:.1f}%)")

        print()
        print(" Prices by location:")
        sorted_prices = sorted(dd['prices_by_location'].items(), key=lambda x: x[1])
        for loc, price in sorted_prices:
            loc_name = LOCATIONS.get(loc, type('obj', (object,), {'name': loc})()).name
            marker = " ★" if loc == dd['best_location'] else ""
            print(f"   {loc} ({loc_name}): ${price:.2f}{marker}")

    # Hidden city geo results
    if results.best_hidden_city_deals:
        print_header("HIDDEN CITY ROUTES GEO COMPARISON", "-")

        for i, hc in enumerate(results.best_hidden_city_deals, 1):
            print(f"\n {i}. {hc['route']} (exit@{hc['exit_at']})")
            print(f"    Best location: {hc['best_location']}")
            print(f"    Best price: ${hc['best_price_usd']:.2f}")
            if hc.get('original_price_usd'):
                print(f"    Original (US): ${hc['original_price_usd']:.2f}")
            print(f"    Airline: {hc['airline']}")
            if hc.get('stops'):
                layover_str = f" via {', '.join(hc['layovers'])}" if hc.get('layovers') else ""
                print(f"    Flight type: {hc['stops']}{layover_str}")

            if hc['potential_savings_usd'] > 0:
                print(f"    Geo savings: ${hc['potential_savings_usd']:.2f}")

            print("    Prices by location:")
            sorted_prices = sorted(hc['prices_by_location'].items(), key=lambda x: x[1])
            for loc, price in sorted_prices:
                marker = " ★" if loc == hc['best_location'] else ""
                print(f"      {loc}: ${price:.2f}{marker}")

    # Overall best deal summary
    print_header("BEST OVERALL DEALS", "-")

    best_deals = []

    # Add direct route
    if results.best_direct_deal:
        best_deals.append({
            'type': 'Direct route',
            'route': results.best_direct_deal['route'],
            'exit': None,
            'price': results.best_direct_deal['best_price_usd'],
            'location': results.best_direct_deal['best_location'],
            'airline': results.best_direct_deal['airline'],
            'stops': results.best_direct_deal.get('stops', ''),
        })

    # Add hidden city routes
    for hc in results.best_hidden_city_deals:
        best_deals.append({
            'type': 'Hidden City',
            'route': hc['route'],
            'exit': hc['exit_at'],
            'price': hc['best_price_usd'],
            'location': hc['best_location'],
            'airline': hc['airline'],
            'stops': hc.get('stops', ''),
        })

    # Sort by price
    best_deals.sort(key=lambda x: x['price'])

    for i, deal in enumerate(best_deals[:5], 1):
        loc_name = LOCATIONS.get(deal['location'], type('obj', (object,), {'name': deal['location']})()).name
        stops_info = f" ({deal['stops']})" if deal.get('stops') else ""
        if deal['exit']:
            print(f" {i}. ${deal['price']:.2f} | {deal['type']} | {deal['route']} exit@{deal['exit']} | {deal['airline']}{stops_info} | {deal['location']} ({loc_name})")
        else:
            print(f" {i}. ${deal['price']:.2f} | {deal['type']} | {deal['route']} | {deal['airline']}{stops_info} | {deal['location']} ({loc_name})")

    # Total savings
    if results.total_potential_savings_usd > 0:
        print_header("TOTAL GEO ARBITRAGE SAVINGS", "-")
        print(f" Total potential savings across all routes: ${results.total_potential_savings_usd:.2f}")

    # Save results
    if save_results:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"geo_hybrid_{origin}_{destination}_{departure_date}_{timestamp}.json"
        output_dir = Path("search_results")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / filename

        with open(output_path, 'w') as f:
            json.dump(results.to_dict(), f, indent=2)

        print_header("OUTPUT", "-")
        print(f" Results saved to: {output_path}")

    print_header("HYBRID GEO SEARCH COMPLETE")

    return results


def push_results_to_github():
    """Push debug files and results to GitHub, then clean up locally."""
    import subprocess
    import time

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
            f"git fetch origin {GIT_BRANCH}",
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
            f"git rebase origin/{GIT_BRANCH}",
            shell=True, capture_output=True
        )

        if rebase_result.returncode != 0:
            print(f" ✗ Rebase conflict - aborting rebase")
            subprocess.run("git rebase --abort", shell=True, capture_output=True)
            # Try to just push anyway - maybe we're ahead
            pass

        # Push using explicit refspec HEAD:<branch> so it works even if
        # the local branch name doesn't exactly match GIT_BRANCH
        print(" Pushing to GitHub...")
        result = subprocess.run(
            f"git push origin HEAD:refs/heads/{GIT_BRANCH}",
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
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Skip syncing with remote before search (use if offline)"
    )

    # Geo arbitrage arguments
    parser.add_argument(
        "--geo", "-g",
        action="store_true",
        help="Enable geo arbitrage: search from multiple locations to compare prices"
    )
    parser.add_argument(
        "--locations", "-l",
        type=str,
        default="BR,US,CO,PA,AR",
        help="Comma-separated location codes for geo search (default: BR,US,CO,PA,AR)"
    )
    parser.add_argument(
        "--proxy-provider",
        type=str,
        help="Proxy provider for Skiplagged (brightdata, oxylabs, smartproxy). Not needed for Google Flights (uses SerpApi gl param)."
    )
    parser.add_argument(
        "--proxy-user",
        type=str,
        help="Proxy username for Skiplagged (or set PROXY_USERNAME env var)"
    )
    parser.add_argument(
        "--proxy-pass",
        type=str,
        help="Proxy password for Skiplagged (or set PROXY_PASSWORD env var)"
    )

    args = parser.parse_args()

    # Sync with remote before search (prevents pull conflicts)
    if not args.no_sync:
        sync_with_remote()

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

    # Check SerpApi key (required for all Google Flights searches)
    serpapi_key = os.environ.get("SERPAPI_KEY", "")
    if not serpapi_key:
        print("WARNING: SERPAPI_KEY not set. Google Flights searches will fail.")
        print("  Set it in your .env file or export SERPAPI_KEY=your_key")
        print()

    # Initialize proxy provider for Skiplagged (from args or environment variables)
    # Note: Google Flights no longer needs proxies (uses SerpApi gl parameter)
    if args.geo:
        init_proxy_provider(
            provider=args.proxy_provider,
            username=args.proxy_user,
            password=args.proxy_pass,
        )

    # Run geo search or regular search
    if args.geo:
        # Parse locations
        locations = [loc.strip().upper() for loc in args.locations.split(",")]
        valid_locations = set(LOCATIONS.keys())
        for loc in locations:
            if loc not in valid_locations:
                print(f"Error: Invalid location '{loc}'. Valid options: {valid_locations}")
                sys.exit(1)

        # Run HYBRID geo arbitrage search
        # Phase 1: Full parallel search (GF + Skiplagged + Hidden City)
        # Phase 2: Geo arbitrage on direct + discovered hidden city routes
        try:
            asyncio.run(run_geo_search(
                origin=args.origin.upper(),
                destination=args.destination.upper(),
                departure_date=departure_date,
                locations=locations,
                headless=not args.visible,
                max_concurrent=args.max_concurrent,
                save_results=not args.no_save,
                quick=args.quick,
            ))
        except RuntimeError as e:
            if "Event loop is closed" not in str(e):
                raise
        except KeyboardInterrupt:
            print("\n Search cancelled by user")
            sys.exit(1)
    else:
        # Run regular parallel search
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
