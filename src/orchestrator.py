"""
Skiplagging Orchestrator
========================
This module orchestrates hidden-city (skiplagging) flight searches by:
1. Taking a true destination B and a list of further destinations C
2. Searching A → C routes using Google Flights
3. Identifying flights where B appears as a layover
4. Returning confirmed hidden-city deals

Hidden City Concept:
- You want to fly A → B (e.g., JFK → PHX)
- Sometimes A → C (e.g., JFK → LAX) is cheaper with a layover at B (PHX)
- You book A → C but get off at B (the layover)
"""

import asyncio
from typing import Optional
from datetime import datetime

from .scraper.google_flights import search_google_flights


async def execute_targeted_skiplag_search(
    origin_A: str,
    destination_B: str,
    date: str,
    target_routes: list[str],
    headless: bool = True,
    max_concurrent: int = 2
) -> list[dict]:
    """
    Search for hidden-city deals by checking multiple A → C routes for B layovers.

    This function searches for flights from origin_A to each destination in
    target_routes, then analyzes the results to find flights where destination_B
    appears as a layover. These represent potential hidden-city fare opportunities.

    Args:
        origin_A: The departure airport/city (e.g., "JFK", "New York")
        destination_B: The true destination - we're looking for this as a layover
                      (e.g., "PHX", "Phoenix")
        date: Departure date in YYYY-MM-DD format
        target_routes: List of 'C' destinations to search (e.g., ["LAX", "SAN", "SFO"])
                      These should be cities beyond B that might have B as a layover
        headless: If True, browser runs invisibly. Set False for debugging.
        max_concurrent: Maximum number of concurrent searches (be gentle on servers)

    Returns:
        List of confirmed hidden-city deal dictionaries. Each dict contains:
        - All original flight data (price, times, airline, etc.)
        - final_destination: The C destination this search was for
        - hidden_city_target: The B destination (your actual target)
        - search_route: String showing "A → C" route searched

    Example:
        # You want to fly JFK → PHX (Phoenix)
        # Search for flights to cities BEYOND Phoenix (West Coast)
        # that might have Phoenix as a layover
        >>> deals = await execute_targeted_skiplag_search(
        ...     origin_A="JFK",
        ...     destination_B="PHX",  # Where you actually want to go
        ...     date="2026-03-15",
        ...     target_routes=["LAX", "SAN", "SFO"]  # Cities beyond PHX
        ... )
        >>> for deal in deals:
        ...     print(f"{deal['price']} - {deal['search_route']} (layover at {deal['hidden_city_target']})")
    """
    confirmed_deals = []
    failed_routes = []

    # Normalize destination_B for matching (handle various formats)
    dest_b_variants = _get_city_variants(destination_B)

    print("=" * 60)
    print("HIDDEN-CITY (SKIPLAGGING) SEARCH")
    print("=" * 60)
    print(f"Origin (A): {origin_A}")
    print(f"Target Destination (B): {destination_B}")
    print(f"  Looking for {destination_B} as a LAYOVER")
    print(f"  Matching variants: {dest_b_variants}")
    print(f"Date: {date}")
    print(f"Searching {len(target_routes)} routes beyond {destination_B}: {', '.join(target_routes)}")
    print("=" * 60)
    print()

    # Process routes with controlled concurrency
    # Using semaphore to limit concurrent browser instances
    semaphore = asyncio.Semaphore(max_concurrent)

    async def search_single_route(dest_C: str) -> list[dict]:
        """Search a single A → C route and check for B layovers."""
        async with semaphore:
            route_deals = []
            search_route = f"{origin_A} → {dest_C}"

            print(f"\n[Searching] {search_route}...")

            try:
                # Search flights from A to C
                flights = await search_google_flights(
                    origin=origin_A,
                    destination=dest_C,
                    departure_date=date,
                    headless=headless
                )

                if not flights:
                    print(f"  No flights found for {search_route}")
                    return route_deals

                print(f"  Found {len(flights)} flights for {search_route}")

                # Analyze each flight for B layovers
                for flight in flights:
                    # Skip flights with errors
                    if flight.get('error') or flight.get('note'):
                        continue

                    # Check if this is a connecting flight (not nonstop)
                    stops = flight.get('stops', '').lower()
                    if 'nonstop' in stops or 'non-stop' in stops:
                        continue  # Nonstop flights can't have layovers

                    # Get layovers list
                    layovers = flight.get('layovers', [])
                    
                    # Debug: show what we're checking
                    if layovers:
                        print(f"    Checking flight {flight.get('price', 'N/A')}: layovers={layovers}")

                    # Check the layovers list for our target destination B
                    has_b_layover = _check_layovers_list(layovers, dest_b_variants)

                    # Fallback: check flight text if layovers list is empty
                    if not has_b_layover and not layovers:
                        flight_text = _get_flight_text(flight)
                        has_b_layover = _check_for_layover(flight_text, dest_b_variants)
                        if has_b_layover:
                            print(f"    Found {destination_B} in flight text (fallback)")

                    if has_b_layover:
                        # Found a potential hidden-city deal!
                        deal = flight.copy()
                        deal['final_destination'] = dest_C
                        deal['hidden_city_target'] = destination_B
                        deal['search_route'] = search_route
                        deal['deal_type'] = 'hidden_city'
                        deal['confirmed_layover'] = True  # Layover was verified
                        route_deals.append(deal)

                        layover_info = f" (layovers: {layovers})" if layovers else ""
                        print(f"  ✓ DEAL FOUND: {flight.get('price', 'N/A')} - "
                              f"Layover at {destination_B}{layover_info}")

                # Also include connecting flights where we couldn't confirm the layover
                # (user can manually verify these)
                connecting_flights = [
                    f for f in flights
                    if 'stop' in f.get('stops', '').lower()
                    and not any(d.get('price') == f.get('price') and
                               d.get('departure_time') == f.get('departure_time')
                               for d in route_deals)
                    and not f.get('error')
                ]

                if connecting_flights:
                    print(f"  + {len(connecting_flights)} other connecting flights (layover not at {destination_B})")
                    for flight in connecting_flights:
                        deal = flight.copy()
                        deal['final_destination'] = dest_C
                        deal['hidden_city_target'] = destination_B
                        deal['search_route'] = search_route
                        deal['confirmed_layover'] = False

                        # Check if we have layover info but it's not the target
                        layovers = flight.get('layovers', [])
                        if layovers:
                            deal['deal_type'] = 'not_target_layover'
                            deal['note'] = f'Layover at {", ".join(layovers)} (not {destination_B})'
                        else:
                            deal['deal_type'] = 'potential_hidden_city'
                            deal['note'] = 'Layover city could not be extracted - verify manually'
                        route_deals.append(deal)

                return route_deals

            except Exception as e:
                print(f"  ✗ Error searching {search_route}: {e}")
                failed_routes.append({'route': search_route, 'error': str(e)})
                return route_deals

    # Execute all searches
    tasks = [search_single_route(dest_C) for dest_C in target_routes]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect all deals
    for result in results:
        if isinstance(result, list):
            confirmed_deals.extend(result)
        elif isinstance(result, Exception):
            print(f"Task exception: {result}")

    # Sort deals by price
    confirmed_deals.sort(key=lambda d: _parse_price(d.get('price', '$999999')))

    # Print summary
    print("\n" + "=" * 60)
    print("SEARCH COMPLETE")
    print("=" * 60)
    print(f"Total routes searched: {len(target_routes)}")
    print(f"Failed routes: {len(failed_routes)}")
    print(f"Potential deals found: {len(confirmed_deals)}")

    if confirmed_deals:
        confirmed_count = sum(1 for d in confirmed_deals if d.get('deal_type') == 'hidden_city')
        potential_count = len(confirmed_deals) - confirmed_count
        print(f"  - Confirmed {destination_B} layovers: {confirmed_count}")
        print(f"  - Other connecting flights: {potential_count}")

    if failed_routes:
        print("\nFailed routes:")
        for fr in failed_routes:
            print(f"  - {fr['route']}: {fr['error']}")

    print("=" * 60)

    return confirmed_deals


def _get_city_variants(city: str) -> list[str]:
    """
    Get various name variants for a city to improve matching.

    Args:
        city: City name or airport code

    Returns:
        List of possible variants to search for
    """
    # Common city/airport mappings
    city_mappings = {
        'LAX': ['LAX', 'Los Angeles', 'LA'],
        'JFK': ['JFK', 'New York', 'NYC', 'Kennedy'],
        'ORD': ['ORD', 'Chicago', "O'Hare", 'OHare'],
        'SFO': ['SFO', 'San Francisco', 'SF'],
        'MIA': ['MIA', 'Miami'],
        'BOS': ['BOS', 'Boston'],
        'SEA': ['SEA', 'Seattle'],
        'DEN': ['DEN', 'Denver'],
        'ATL': ['ATL', 'Atlanta'],
        'DFW': ['DFW', 'Dallas', 'Fort Worth'],
        'PHX': ['PHX', 'Phoenix'],
        'LAS': ['LAS', 'Las Vegas', 'Vegas'],
        'SAN': ['SAN', 'San Diego'],
        'PDX': ['PDX', 'Portland'],
        'CLT': ['CLT', 'Charlotte'],
        'DTW': ['DTW', 'Detroit'],
        'MSP': ['MSP', 'Minneapolis'],
        'MCO': ['MCO', 'Orlando'],
        'EWR': ['EWR', 'Newark'],
        'IAH': ['IAH', 'Houston'],
        'AUS': ['AUS', 'Austin'],
        'SLC': ['SLC', 'Salt Lake City'],
    }

    city_upper = city.upper().strip()

    # If it's a known airport code, return all variants
    if city_upper in city_mappings:
        return city_mappings[city_upper]

    # Check if the city name matches any mapping
    city_lower = city.lower().strip()
    for code, variants in city_mappings.items():
        for variant in variants:
            if variant.lower() == city_lower:
                return city_mappings[code]

    # Default: return the city and common variations
    return [city, city.upper(), city.lower(), city.title()]


def _get_flight_text(flight: dict) -> str:
    """
    Concatenate all flight info into searchable text.

    Args:
        flight: Flight dictionary

    Returns:
        Combined text from all flight fields
    """
    parts = []
    for key, value in flight.items():
        if value and isinstance(value, str):
            parts.append(value)
    return ' '.join(parts).lower()


def _check_layovers_list(layovers: list[str], city_variants: list[str]) -> bool:
    """
    Check if any city variant appears in the layovers list.

    This is the preferred method when the scraper has extracted explicit
    layover airport codes from the flight details.

    Args:
        layovers: List of airport codes from the flight (e.g., ['LAX', 'DEN'])
        city_variants: List of city name/code variants to search for

    Returns:
        True if a layover at the target city is detected
    """
    if not layovers:
        return False

    # Normalize layovers to uppercase for comparison
    layovers_upper = [code.upper().strip() for code in layovers]

    for variant in city_variants:
        variant_upper = variant.upper().strip()
        
        # Direct match with airport code
        if variant_upper in layovers_upper:
            return True
        
        # Also check partial matches (for city names in layover data)
        for layover in layovers_upper:
            # Check if the 3-letter code matches
            if len(variant_upper) == 3 and variant_upper == layover:
                return True
            # Check if city name contains the layover code or vice versa
            if len(variant_upper) > 3:
                if layover in variant_upper or variant_upper in layover:
                    return True

    return False


def _check_for_layover(flight_text: str, city_variants: list[str]) -> bool:
    """
    Check if any city variant appears in the flight text.

    This is a fallback method when explicit layover data is not available.

    Args:
        flight_text: Combined flight information text
        city_variants: List of city name variants to search for

    Returns:
        True if a layover at the target city is detected
    """
    flight_lower = flight_text.lower()

    for variant in city_variants:
        if variant.lower() in flight_lower:
            return True

    return False


def _parse_price(price_str: str) -> int:
    """
    Parse a price string to an integer for sorting.

    Args:
        price_str: Price string like "$299", "US$1,234", etc.

    Returns:
        Integer price value, or 999999 if parsing fails
    """
    try:
        # Remove currency symbols, commas, spaces
        cleaned = ''.join(c for c in price_str if c.isdigit())
        return int(cleaned) if cleaned else 999999
    except:
        return 999999


async def search_skiplag_deals(
    origin: str,
    destination: str,
    date: str,
    target_routes: Optional[list[str]] = None,
    headless: bool = True
) -> list[dict]:
    """
    Convenience wrapper with auto-generated target routes if not provided.

    For common routes, this will automatically suggest potential C destinations
    (cities beyond the destination that might have it as a layover).

    Args:
        origin: Departure city/airport
        destination: True destination (will look for this as layover)
        date: Departure date (YYYY-MM-DD)
        target_routes: Optional list of C destinations. If None, uses defaults.
        headless: Browser visibility

    Returns:
        List of potential hidden-city deals
    """
    # Default target routes for common destinations
    # Key = where you want to go (B)
    # Value = cities BEYOND B that might have B as a layover (C destinations)
    default_targets = {
        # If you want to go to PHX, search for flights to West Coast cities
        # that might stop in Phoenix
        'PHX': ['LAX', 'SAN', 'SFO', 'PDX', 'SEA'],
        # If you want to go to DEN, search for flights to West Coast
        'DEN': ['LAX', 'SFO', 'SEA', 'PDX', 'SAN', 'LAS'],
        # If you want to go to DFW, search for flights further west/south
        'DFW': ['LAX', 'SAN', 'PHX', 'LAS', 'SFO'],
        # If you want to go to ATL, search for flights to Florida/Caribbean
        'ATL': ['MIA', 'FLL', 'TPA', 'MCO', 'SJU'],
        # If you want to go to ORD, search for flights further west
        'ORD': ['LAX', 'SFO', 'SEA', 'DEN', 'PHX'],
        # If you want to go to CLT, search for flights to Florida
        'CLT': ['MIA', 'FLL', 'TPA', 'MCO'],
        # If you want to go to LAX, search for international/Hawaii
        'LAX': ['HNL', 'SYD', 'NRT', 'HKG'],
        # If you want to go to SFO, search for Asia/Hawaii
        'SFO': ['HNL', 'NRT', 'HKG', 'TPE'],
    }

    if target_routes is None:
        dest_upper = destination.upper()
        if dest_upper in default_targets:
            target_routes = default_targets[dest_upper]
            print(f"Using default target routes for {destination}: {target_routes}")
            print(f"(Searching for flights TO these cities that STOP at {destination})")
        else:
            print(f"No default targets for {destination}. Please provide target_routes.")
            print(f"Hint: target_routes should be cities BEYOND {destination}")
            return []

    return await execute_targeted_skiplag_search(
        origin_A=origin,
        destination_B=destination,
        date=date,
        target_routes=target_routes,
        headless=headless
    )


# ============================================================================
# CLI INTERFACE
# ============================================================================
if __name__ == "__main__":
    import sys

    async def main():
        """Command-line interface for the orchestrator."""
        print("=" * 60)
        print("SKIPLAGGING DEAL FINDER")
        print("=" * 60)

        # Example usage
        if len(sys.argv) < 4:
            print("\nUsage: python orchestrator.py <origin> <destination> <date> [target1,target2,...]")
            print("\nExample:")
            print("  python orchestrator.py JFK PHX 2026-03-15 LAX,SAN,SFO")
            print("\nThis searches JFK→LAX, JFK→SAN, JFK→SFO looking for PHX layovers")
            print("(You want to go to PHX, so search flights to cities BEYOND PHX)")
            return

        origin = sys.argv[1]
        destination = sys.argv[2]
        date = sys.argv[3]

        if len(sys.argv) > 4:
            target_routes = sys.argv[4].split(',')
        else:
            target_routes = None  # Will use defaults

        deals = await search_skiplag_deals(
            origin=origin,
            destination=destination,
            date=date,
            target_routes=target_routes,
            headless=True
        )

        if deals:
            print("\n" + "=" * 60)
            print("POTENTIAL DEALS")
            print("=" * 60)

            for i, deal in enumerate(deals, 1):
                deal_type = "✓ CONFIRMED" if deal.get('deal_type') == 'hidden_city' else "? POTENTIAL"
                print(f"\n[{i}] {deal_type}")
                print(f"    Route: {deal.get('search_route', 'N/A')}")
                print(f"    Price: {deal.get('price', 'N/A')}")
                print(f"    Times: {deal.get('departure_time', 'N/A')} → {deal.get('arrival_time', 'N/A')}")
                print(f"    Duration: {deal.get('duration', 'N/A')}")
                print(f"    Stops: {deal.get('stops', 'N/A')}")
                print(f"    Airline: {deal.get('airline', 'N/A')}")
                print(f"    Layovers: {deal.get('layovers', [])}")
                if deal.get('note'):
                    print(f"    Note: {deal.get('note')}")
        else:
            print("\nNo deals found. Try different target routes or dates.")

    asyncio.run(main())
