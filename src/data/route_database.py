"""
Route Database for Skiplagging Searches
========================================

This module contains mappings of destinations (B) to potential "beyond" cities (C)
that frequently have B as a layover.

Two-tier lookup system:
1. ORIGIN_SPECIFIC_ROUTES - Custom C routes for specific A→B combinations
2. ROUTE_DATABASE - Default C routes for any origin to B (fallback)

The key insight: If you want to fly to city B, search for flights to cities C
that are BEYOND B geographically. Airlines often route through B as a hub.

Usage:
    from src.data.route_database import get_target_routes, ROUTE_DATABASE

    # Get routes for specific origin-destination pair
    targets = get_target_routes("JFK", "DEN")  # Checks JFK→DEN specific, then defaults

    # Get default routes for any origin
    targets = get_target_routes(destination="DEN")  # Returns default ['LAX', 'SFO', ...]
"""

# =============================================================================
# ORIGIN-SPECIFIC ROUTES (A → B specific C destinations)
# =============================================================================
# Key = Origin airport (A)
# Value = Dict of destination (B) → list of C destinations
#
# These override the default ROUTE_DATABASE when a specific A→B combo is defined.
# Use this for routes where you know specific airlines/hubs work better.
# =============================================================================

ORIGIN_SPECIFIC_ROUTES = {
    # -------------------------------------------------------------------------
    # NEW YORK AREA ORIGINS
    # -------------------------------------------------------------------------
    "JFK": {
        # JFK → Denver: United flies through DEN to West Coast
        "DEN": ["LAX", "SFO", "SEA", "PDX", "SAN", "LAS"],
        # JFK → Phoenix: American routes through PHX
        "PHX": ["LAX", "SAN", "SFO", "LAS", "PDX"],
        # JFK → Atlanta: Delta hub, routes to Florida/Caribbean
        "ATL": ["MIA", "FLL", "TPA", "MCO", "SJU", "CUN"],
        # JFK → Dallas: American mega-hub
        "DFW": ["LAX", "SFO", "PHX", "LAS", "SAN", "SEA"],
        # JFK → Chicago: Common connection point
        "ORD": ["LAX", "SFO", "SEA", "DEN", "PHX", "LAS"],
        # JFK → Charlotte: American hub to Florida
        "CLT": ["MIA", "FLL", "TPA", "MCO", "SJU"],
        # JFK → Salt Lake City: Delta hub
        "SLC": ["LAX", "SFO", "SEA", "PDX", "SAN"],
        # JFK → Minneapolis: Delta hub
        "MSP": ["SEA", "PDX", "SFO", "LAX", "ANC"],
    },

    "EWR": {
        # Newark is United hub - different routing than JFK
        "DEN": ["LAX", "SFO", "SEA", "PDX", "SAN", "LAS", "PHX"],
        "IAH": ["LAX", "SFO", "PHX", "LAS", "MEX", "CUN"],
        "ORD": ["LAX", "SFO", "SEA", "DEN", "PHX"],
        "SFO": ["HNL", "NRT", "HKG", "TPE"],  # United Pacific routes
    },

    "LGA": {
        # LaGuardia - mostly domestic, Delta/American focus
        "ATL": ["MIA", "FLL", "TPA", "MCO", "SJU"],
        "DFW": ["LAX", "PHX", "LAS", "SAN"],
        "ORD": ["LAX", "SFO", "DEN", "PHX"],
        "CLT": ["MIA", "FLL", "TPA"],
    },

    # -------------------------------------------------------------------------
    # BOSTON AREA
    # -------------------------------------------------------------------------
    "BOS": {
        # Boston often routes through NYC hubs or direct to hubs
        "DEN": ["LAX", "SFO", "SEA", "PDX", "LAS"],
        "ATL": ["MIA", "FLL", "TPA", "MCO"],
        "DFW": ["LAX", "PHX", "SAN", "LAS"],
        "ORD": ["LAX", "SFO", "SEA", "DEN"],
        "CLT": ["MIA", "FLL", "TPA", "MCO"],
        "PHX": ["LAX", "SAN", "SFO"],
    },

    # -------------------------------------------------------------------------
    # WASHINGTON DC AREA
    # -------------------------------------------------------------------------
    "IAD": {
        # Dulles is United hub
        "DEN": ["LAX", "SFO", "SEA", "PDX", "SAN"],
        "ORD": ["LAX", "SFO", "SEA", "DEN"],
        "IAH": ["LAX", "SFO", "MEX", "CUN"],
        "SFO": ["HNL", "NRT", "HKG"],
    },

    "DCA": {
        # Reagan National - American focus
        "DFW": ["LAX", "PHX", "SAN", "LAS"],
        "CLT": ["MIA", "FLL", "TPA"],
        "ORD": ["LAX", "SFO", "DEN"],
        "PHX": ["LAX", "SAN", "SFO"],
    },

    # -------------------------------------------------------------------------
    # CHICAGO ORIGINS (when ORD is origin, not destination)
    # -------------------------------------------------------------------------
    "ORD": {
        # From Chicago to West Coast, often through DEN or direct
        "DEN": ["LAX", "SFO", "SEA", "PDX", "SAN"],
        "PHX": ["LAX", "SAN", "SFO"],
        "SLC": ["LAX", "SFO", "SEA", "PDX"],
        "DFW": ["LAX", "PHX", "SAN"],
    },

    # -------------------------------------------------------------------------
    # LOS ANGELES ORIGINS (reverse direction)
    # -------------------------------------------------------------------------
    "LAX": {
        # LAX eastbound through hubs
        "DEN": ["JFK", "EWR", "BOS", "ORD", "MIA"],
        "DFW": ["JFK", "EWR", "BOS", "MIA", "ATL"],
        "ORD": ["JFK", "EWR", "BOS", "MIA"],
        "ATL": ["JFK", "EWR", "BOS", "MIA"],
        "IAH": ["JFK", "EWR", "MIA", "ATL"],
    },

    # -------------------------------------------------------------------------
    # SAN FRANCISCO ORIGINS
    # -------------------------------------------------------------------------
    "SFO": {
        "DEN": ["JFK", "EWR", "BOS", "ORD", "MIA"],
        "ORD": ["JFK", "EWR", "BOS", "MIA"],
        "IAH": ["JFK", "EWR", "MIA", "ATL"],
        "DFW": ["JFK", "EWR", "BOS", "MIA"],
    },

    # -------------------------------------------------------------------------
    # MIAMI/FLORIDA ORIGINS
    # -------------------------------------------------------------------------
    "MIA": {
        # Miami northbound through ATL/CLT
        "ATL": ["JFK", "EWR", "BOS", "ORD", "DEN"],
        "CLT": ["JFK", "EWR", "BOS", "ORD"],
        "DFW": ["LAX", "SFO", "SEA", "PHX"],
        "IAH": ["LAX", "SFO", "MEX"],
    },

    # -------------------------------------------------------------------------
    # ATLANTA ORIGINS
    # -------------------------------------------------------------------------
    "ATL": {
        # Atlanta westbound
        "DEN": ["LAX", "SFO", "SEA", "PDX"],
        "DFW": ["LAX", "SFO", "PHX", "SAN"],
        "PHX": ["LAX", "SAN", "SFO"],
        "SLC": ["LAX", "SFO", "SEA"],
    },

    # -------------------------------------------------------------------------
    # SEATTLE ORIGINS
    # -------------------------------------------------------------------------
    "SEA": {
        "DEN": ["JFK", "EWR", "BOS", "MIA", "ATL"],
        "SLC": ["JFK", "EWR", "ORD", "ATL"],
        "PHX": ["JFK", "EWR", "ORD", "MIA", "ATL"],
    },
}


# =============================================================================
# ROUTE DATABASE (Default fallback routes)
# =============================================================================
# Key = Your true destination (B) - where you actually want to go
# Value = Cities BEYOND B (C destinations) that often have B as a layover
#
# These are used when no origin-specific route is defined.
# Organized by geographic region and hub status.
# =============================================================================

ROUTE_DATABASE = {
    # -------------------------------------------------------------------------
    # MAJOR HUBS - High probability of being layover cities
    # -------------------------------------------------------------------------

    # Denver (DEN) - Major United hub, gateway to West
    "DEN": {
        "targets": ["LAX", "SFO", "SEA", "PDX", "SAN", "LAS", "PHX", "SLC", "OAK"],
        "hub_for": ["United"],
        "notes": "Major connecting hub for East→West flights"
    },

    # Dallas/Fort Worth (DFW) - Major American hub
    "DFW": {
        "targets": ["LAX", "SAN", "PHX", "LAS", "SFO", "SEA", "PDX", "TUS", "ABQ"],
        "hub_for": ["American"],
        "notes": "American Airlines mega-hub, routes to West/Southwest"
    },

    # Atlanta (ATL) - Delta's main hub, busiest US airport
    "ATL": {
        "targets": ["MIA", "FLL", "TPA", "MCO", "PBI", "JAX", "SJU", "RSW", "MSY"],
        "hub_for": ["Delta"],
        "notes": "Delta's main hub, gateway to Florida/Caribbean"
    },

    # Chicago O'Hare (ORD) - United/American hub
    "ORD": {
        "targets": ["LAX", "SFO", "SEA", "DEN", "PHX", "LAS", "PDX", "SAN"],
        "hub_for": ["United", "American"],
        "notes": "Major Midwest hub for transcontinental flights"
    },

    # Phoenix (PHX) - American hub, Southwest focus
    "PHX": {
        "targets": ["LAX", "SAN", "SFO", "PDX", "SEA", "OAK", "ONT", "SMF"],
        "hub_for": ["American", "Southwest"],
        "notes": "Gateway to Southern California"
    },

    # Charlotte (CLT) - American hub
    "CLT": {
        "targets": ["MIA", "FLL", "TPA", "MCO", "PBI", "RSW", "JAX", "SJU"],
        "hub_for": ["American"],
        "notes": "American hub, routes to Florida/Caribbean"
    },

    # Houston (IAH) - United hub
    "IAH": {
        "targets": ["LAX", "SFO", "PHX", "LAS", "SAN", "MEX", "CUN", "GDL"],
        "hub_for": ["United"],
        "notes": "United hub, gateway to Mexico/Latin America"
    },

    # Minneapolis (MSP) - Delta hub
    "MSP": {
        "targets": ["SEA", "PDX", "SFO", "LAX", "ANC", "DEN"],
        "hub_for": ["Delta"],
        "notes": "Delta hub, routes to Pacific Northwest/Alaska"
    },

    # Salt Lake City (SLC) - Delta hub
    "SLC": {
        "targets": ["LAX", "SFO", "SEA", "PDX", "SAN", "OAK", "SMF"],
        "hub_for": ["Delta"],
        "notes": "Delta hub for West Coast routes"
    },

    # Detroit (DTW) - Delta hub
    "DTW": {
        "targets": ["LAX", "SFO", "SEA", "LAS", "PHX", "DEN"],
        "hub_for": ["Delta"],
        "notes": "Delta hub, transcontinental routes"
    },

    # -------------------------------------------------------------------------
    # WEST COAST DESTINATIONS
    # -------------------------------------------------------------------------

    # Los Angeles (LAX)
    "LAX": {
        "targets": ["HNL", "OGG", "LIH", "KOA", "SYD", "NRT", "HKG", "TPE", "ICN"],
        "hub_for": ["American", "United", "Delta"],
        "notes": "Gateway to Hawaii/Asia-Pacific"
    },

    # San Francisco (SFO)
    "SFO": {
        "targets": ["HNL", "OGG", "NRT", "HKG", "TPE", "ICN", "SIN", "PVG"],
        "hub_for": ["United"],
        "notes": "United hub, gateway to Asia"
    },

    # Seattle (SEA)
    "SEA": {
        "targets": ["ANC", "FAI", "HNL", "NRT", "ICN", "PVG", "HKG"],
        "hub_for": ["Alaska", "Delta"],
        "notes": "Alaska Airlines hub, gateway to Alaska/Asia"
    },

    # Las Vegas (LAS)
    "LAS": {
        "targets": ["LAX", "SFO", "SAN", "HNL"],
        "hub_for": ["Southwest", "Spirit"],
        "notes": "Popular leisure destination, often a connection point"
    },

    # San Diego (SAN)
    "SAN": {
        "targets": ["HNL", "OGG"],
        "hub_for": [],
        "notes": "Limited hub activity, mostly point-to-point"
    },

    # Portland (PDX)
    "PDX": {
        "targets": ["ANC", "HNL", "OGG"],
        "hub_for": ["Alaska"],
        "notes": "Alaska Airlines focus city"
    },

    # -------------------------------------------------------------------------
    # FLORIDA DESTINATIONS
    # -------------------------------------------------------------------------

    # Miami (MIA)
    "MIA": {
        "targets": ["SJU", "STT", "STX", "BOG", "LIM", "GRU", "SCL", "EZE"],
        "hub_for": ["American"],
        "notes": "Gateway to Caribbean/South America"
    },

    # Orlando (MCO)
    "MCO": {
        "targets": ["SJU", "STT", "CUN", "MBJ"],
        "hub_for": [],
        "notes": "Major tourist destination"
    },

    # Fort Lauderdale (FLL)
    "FLL": {
        "targets": ["SJU", "STT", "CUN", "MBJ", "NAS"],
        "hub_for": ["Spirit", "JetBlue"],
        "notes": "Low-cost carrier hub, Caribbean gateway"
    },

    # Tampa (TPA)
    "TPA": {
        "targets": ["SJU", "CUN", "MBJ"],
        "hub_for": [],
        "notes": "Florida Gulf Coast hub"
    },

    # -------------------------------------------------------------------------
    # TEXAS DESTINATIONS
    # -------------------------------------------------------------------------

    # Austin (AUS)
    "AUS": {
        "targets": ["LAX", "SFO", "SEA", "MEX", "CUN"],
        "hub_for": [],
        "notes": "Growing tech hub, increasing flight options"
    },

    # San Antonio (SAT)
    "SAT": {
        "targets": ["LAX", "PHX", "LAS", "MEX"],
        "hub_for": [],
        "notes": "Southwest focus city"
    },

    # -------------------------------------------------------------------------
    # OTHER DESTINATIONS
    # -------------------------------------------------------------------------

    # Nashville (BNA)
    "BNA": {
        "targets": ["LAX", "SFO", "SEA", "MIA", "DEN"],
        "hub_for": ["Southwest"],
        "notes": "Growing hub, many connections"
    },

    # New Orleans (MSY)
    "MSY": {
        "targets": ["LAX", "SFO", "CUN", "MBJ"],
        "hub_for": [],
        "notes": "Tourist destination, limited hub activity"
    },

    # Boston (BOS)
    "BOS": {
        "targets": ["LAX", "SFO", "SEA", "DUB", "LHR"],
        "hub_for": ["JetBlue"],
        "notes": "JetBlue focus city, transatlantic gateway"
    },

    # Washington Dulles (IAD)
    "IAD": {
        "targets": ["LAX", "SFO", "SEA", "LHR", "FRA", "CDG"],
        "hub_for": ["United"],
        "notes": "United hub, transatlantic/transcontinental"
    },

    # Raleigh-Durham (RDU)
    "RDU": {
        "targets": ["LAX", "SFO", "SEA", "MIA"],
        "hub_for": [],
        "notes": "Growing market, connections via major hubs"
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_target_routes(
    destination: str,
    origin: str = None,
    limit: int = None
) -> tuple[list[str], bool]:
    """
    Get suggested target routes (C destinations) for a given A→B route.

    Checks origin-specific routes first, then falls back to default routes.

    Args:
        destination: Airport code of your true destination B (e.g., "DEN")
        origin: Optional origin airport A (e.g., "JFK") for specific routing
        limit: Optional limit on number of targets to return

    Returns:
        Tuple of (list of airport codes, is_origin_specific)
        - List of C destinations to search
        - Boolean indicating if origin-specific routes were found
    """
    dest_upper = destination.upper().strip()
    is_specific = False
    targets = []

    # First, check origin-specific routes
    if origin:
        origin_upper = origin.upper().strip()
        if origin_upper in ORIGIN_SPECIFIC_ROUTES:
            origin_routes = ORIGIN_SPECIFIC_ROUTES[origin_upper]
            if dest_upper in origin_routes:
                targets = origin_routes[dest_upper]
                is_specific = True

    # Fall back to default routes if no origin-specific found
    if not targets and dest_upper in ROUTE_DATABASE:
        targets = ROUTE_DATABASE[dest_upper]["targets"]

    # Apply limit if specified
    if limit and targets:
        targets = targets[:limit]

    return targets, is_specific


def get_destination_info(destination: str) -> dict:
    """
    Get full info about a destination including targets and notes.

    Args:
        destination: Airport code

    Returns:
        Dictionary with targets, hub_for, and notes
    """
    dest_upper = destination.upper().strip()
    return ROUTE_DATABASE.get(dest_upper, {})


def list_supported_destinations() -> list[str]:
    """
    Get list of all supported destination codes (from default routes).

    Returns:
        Sorted list of airport codes in the database
    """
    return sorted(ROUTE_DATABASE.keys())


def list_supported_origins() -> list[str]:
    """
    Get list of origins that have specific route configurations.

    Returns:
        Sorted list of origin airport codes with custom routes
    """
    return sorted(ORIGIN_SPECIFIC_ROUTES.keys())


def get_origin_specific_destinations(origin: str) -> list[str]:
    """
    Get list of destinations that have specific routes from a given origin.

    Args:
        origin: Origin airport code

    Returns:
        List of destination codes with custom routes from this origin
    """
    origin_upper = origin.upper().strip()
    if origin_upper in ORIGIN_SPECIFIC_ROUTES:
        return sorted(ORIGIN_SPECIFIC_ROUTES[origin_upper].keys())
    return []


def search_by_hub_airline(airline: str) -> list[str]:
    """
    Find destinations that are hubs for a specific airline.

    Args:
        airline: Airline name (e.g., "United", "Delta")

    Returns:
        List of airport codes that are hubs for that airline
    """
    airline_lower = airline.lower()
    hubs = []
    for code, info in ROUTE_DATABASE.items():
        for hub_airline in info.get("hub_for", []):
            if airline_lower in hub_airline.lower():
                hubs.append(code)
    return sorted(hubs)


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        # Origin and destination provided
        origin = sys.argv[1]
        dest = sys.argv[2]
        targets, is_specific = get_target_routes(dest, origin)

        print(f"\n{origin.upper()} → {dest.upper()} Route Information:")
        if is_specific:
            print(f"  [ORIGIN-SPECIFIC ROUTES]")
        else:
            print(f"  [DEFAULT ROUTES - no {origin}→{dest} specific config]")
        print(f"  Targets: {', '.join(targets) if targets else 'None found'}")

        info = get_destination_info(dest)
        if info:
            print(f"  Hub for: {', '.join(info.get('hub_for', [])) or 'N/A'}")
            print(f"  Notes: {info.get('notes', 'N/A')}")

    elif len(sys.argv) > 1:
        dest = sys.argv[1]
        info = get_destination_info(dest)
        if info:
            print(f"\n{dest.upper()} Default Route Information:")
            print(f"  Targets: {', '.join(info.get('targets', []))}")
            print(f"  Hub for: {', '.join(info.get('hub_for', [])) or 'N/A'}")
            print(f"  Notes: {info.get('notes', 'N/A')}")

            # Show which origins have specific routes for this destination
            specific_origins = []
            for orig in ORIGIN_SPECIFIC_ROUTES:
                if dest.upper() in ORIGIN_SPECIFIC_ROUTES[orig]:
                    specific_origins.append(orig)
            if specific_origins:
                print(f"\n  Origins with specific routes to {dest.upper()}:")
                for orig in sorted(specific_origins):
                    targets = ORIGIN_SPECIFIC_ROUTES[orig][dest.upper()]
                    print(f"    {orig}: {', '.join(targets[:4])}...")
        else:
            print(f"\n{dest.upper()} not found in database.")
            print(f"\nSupported destinations: {', '.join(list_supported_destinations())}")
    else:
        print("\nUsage:")
        print("  python -m src.data.route_database <destination>")
        print("  python -m src.data.route_database <origin> <destination>")
        print("\nSupported Destinations (default routes):")
        print("-" * 50)
        for code in list_supported_destinations():
            info = ROUTE_DATABASE[code]
            targets = info["targets"][:3]
            print(f"  {code}: {', '.join(targets)}...")

        print("\nOrigins with specific routes:")
        print("-" * 50)
        for origin in list_supported_origins():
            dests = get_origin_specific_destinations(origin)
            print(f"  {origin}: → {', '.join(dests)}")
