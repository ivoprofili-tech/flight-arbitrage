"""
Route Database for Skiplagging Searches
========================================

This module contains mappings for hidden-city flight searches.

Two-tier lookup system:
1. PAIR_ROUTES - Custom C destinations for specific A→B pairs
2. ROUTE_DATABASE - Default C destinations for any origin to B (fallback)

The key insight: If you want to fly A→B, search for flights A→C where C is
BEYOND B geographically. Airlines often route through B as a hub.

Usage:
    from src.data.route_database import get_target_routes, ROUTE_DATABASE

    # Get routes for specific A→B pair (checks pair-specific first, then defaults)
    targets, is_pair_specific = get_target_routes("DEN", origin="JFK")

    # Get default routes for destination B (any origin)
    targets, _ = get_target_routes("DEN")  # Returns default ['LAX', 'SFO', ...]
"""

# =============================================================================
# PAIR-SPECIFIC ROUTES (A→B pair determines C destinations)
# =============================================================================
# Key = Tuple of (origin_A, destination_B)
# Value = List of C destinations to search
#
# These override ROUTE_DATABASE when a specific A→B pair is defined.
# The combination of origin AND destination determines which C routes to search.
#
# Example: JFK→DEN and LAX→DEN have different C targets because:
#   - JFK→DEN: Search westbound (LAX, SFO, SEA) - flights continue west
#   - LAX→DEN: Search eastbound (JFK, BOS, MIA) - flights continue east
# =============================================================================

PAIR_ROUTES = {
    # =========================================================================
    # NEW YORK AREA → Various Destinations
    # =========================================================================

    # JFK (Kennedy) pairs
    ("JFK", "DEN"): ["LAX", "SFO", "SEA", "PDX", "SAN", "LAS"],  # United westbound
    ("JFK", "PHX"): ["LAX", "SAN", "SFO", "LAS", "PDX"],  # American westbound
    ("JFK", "ATL"): ["MIA", "FLL", "TPA", "MCO", "SJU", "CUN"],  # Delta southbound
    ("JFK", "DFW"): ["LAX", "SFO", "PHX", "LAS", "SAN", "SEA"],  # American westbound
    ("JFK", "ORD"): ["LAX", "SFO", "SEA", "DEN", "PHX", "LAS"],  # Westbound connections
    ("JFK", "CLT"): ["MIA", "FLL", "TPA", "MCO", "SJU"],  # American to Florida
    ("JFK", "SLC"): ["LAX", "SFO", "SEA", "PDX", "SAN"],  # Delta westbound
    ("JFK", "MSP"): ["SEA", "PDX", "SFO", "LAX", "ANC"],  # Delta to Pacific NW

    # EWR (Newark) pairs - United hub, different routing than JFK
    ("EWR", "DEN"): ["LAX", "SFO", "SEA", "PDX", "SAN", "LAS", "PHX"],
    ("EWR", "IAH"): ["LAX", "SFO", "PHX", "LAS", "MEX", "CUN"],
    ("EWR", "ORD"): ["LAX", "SFO", "SEA", "DEN", "PHX"],
    ("EWR", "SFO"): ["HNL", "NRT", "HKG", "TPE"],  # United Pacific routes

    # LGA (LaGuardia) pairs - mostly domestic Delta/American
    ("LGA", "ATL"): ["MIA", "FLL", "TPA", "MCO", "SJU"],
    ("LGA", "DFW"): ["LAX", "PHX", "LAS", "SAN"],
    ("LGA", "ORD"): ["LAX", "SFO", "DEN", "PHX"],
    ("LGA", "CLT"): ["MIA", "FLL", "TPA"],

    # =========================================================================
    # BOSTON → Various Destinations
    # =========================================================================
    ("BOS", "DEN"): ["LAX", "SFO", "SEA", "PDX", "LAS"],
    ("BOS", "ATL"): ["MIA", "FLL", "TPA", "MCO"],
    ("BOS", "DFW"): ["LAX", "PHX", "SAN", "LAS"],
    ("BOS", "ORD"): ["LAX", "SFO", "SEA", "DEN"],
    ("BOS", "CLT"): ["MIA", "FLL", "TPA", "MCO"],
    ("BOS", "PHX"): ["LAX", "SAN", "SFO"],

    # =========================================================================
    # WASHINGTON DC AREA → Various Destinations
    # =========================================================================

    # IAD (Dulles) pairs - United hub
    ("IAD", "DEN"): ["LAX", "SFO", "SEA", "PDX", "SAN"],
    ("IAD", "ORD"): ["LAX", "SFO", "SEA", "DEN"],
    ("IAD", "IAH"): ["LAX", "SFO", "MEX", "CUN"],
    ("IAD", "SFO"): ["HNL", "NRT", "HKG"],

    # DCA (Reagan National) pairs - American focus
    ("DCA", "DFW"): ["LAX", "PHX", "SAN", "LAS"],
    ("DCA", "CLT"): ["MIA", "FLL", "TPA"],
    ("DCA", "ORD"): ["LAX", "SFO", "DEN"],
    ("DCA", "PHX"): ["LAX", "SAN", "SFO"],

    # =========================================================================
    # CHICAGO → Various Destinations (ORD as origin)
    # =========================================================================
    ("ORD", "DEN"): ["LAX", "SFO", "SEA", "PDX", "SAN"],
    ("ORD", "PHX"): ["LAX", "SAN", "SFO"],
    ("ORD", "SLC"): ["LAX", "SFO", "SEA", "PDX"],
    ("ORD", "DFW"): ["LAX", "PHX", "SAN"],

    # =========================================================================
    # LOS ANGELES → Various Destinations (Eastbound)
    # =========================================================================
    ("LAX", "DEN"): ["JFK", "EWR", "BOS", "ORD", "MIA"],
    ("LAX", "DFW"): ["JFK", "EWR", "BOS", "MIA", "ATL"],
    ("LAX", "ORD"): ["JFK", "EWR", "BOS", "MIA"],
    ("LAX", "ATL"): ["JFK", "EWR", "BOS", "MIA"],
    ("LAX", "IAH"): ["JFK", "EWR", "MIA", "ATL"],

    # =========================================================================
    # SAN FRANCISCO → Various Destinations (Eastbound)
    # =========================================================================
    ("SFO", "DEN"): ["JFK", "EWR", "BOS", "ORD", "MIA"],
    ("SFO", "ORD"): ["JFK", "EWR", "BOS", "MIA"],
    ("SFO", "IAH"): ["JFK", "EWR", "MIA", "ATL"],
    ("SFO", "DFW"): ["JFK", "EWR", "BOS", "MIA"],

    # =========================================================================
    # MIAMI → Various Destinations (Northbound/Westbound)
    # =========================================================================
    ("MIA", "ATL"): ["JFK", "EWR", "BOS", "ORD", "DEN"],
    ("MIA", "CLT"): ["JFK", "EWR", "BOS", "ORD"],
    ("MIA", "DFW"): ["LAX", "SFO", "SEA", "PHX"],
    ("MIA", "IAH"): ["LAX", "SFO", "MEX"],

    # =========================================================================
    # ATLANTA → Various Destinations (Westbound)
    # =========================================================================
    ("ATL", "DEN"): ["LAX", "SFO", "SEA", "PDX"],
    ("ATL", "DFW"): ["LAX", "SFO", "PHX", "SAN"],
    ("ATL", "PHX"): ["LAX", "SAN", "SFO"],
    ("ATL", "SLC"): ["LAX", "SFO", "SEA"],

    # =========================================================================
    # SEATTLE → Various Destinations (Eastbound)
    # =========================================================================
    ("SEA", "DEN"): ["JFK", "EWR", "BOS", "MIA", "ATL"],
    ("SEA", "SLC"): ["JFK", "EWR", "ORD", "ATL"],
    ("SEA", "PHX"): ["JFK", "EWR", "ORD", "MIA", "ATL"],
}

# Legacy alias for backwards compatibility
ORIGIN_SPECIFIC_ROUTES = None  # Deprecated - use PAIR_ROUTES instead


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

    Checks pair-specific routes first, then falls back to default routes.

    Args:
        destination: Airport code of your true destination B (e.g., "DEN")
        origin: Optional origin airport A (e.g., "JFK") for pair-specific routing
        limit: Optional limit on number of targets to return

    Returns:
        Tuple of (list of airport codes, is_pair_specific)
        - List of C destinations to search
        - Boolean indicating if pair-specific routes were found
    """
    dest_upper = destination.upper().strip()
    is_pair_specific = False
    targets = []

    # First, check pair-specific routes (A, B) → C
    if origin:
        origin_upper = origin.upper().strip()
        pair_key = (origin_upper, dest_upper)
        if pair_key in PAIR_ROUTES:
            targets = PAIR_ROUTES[pair_key].copy()
            is_pair_specific = True

    # Fall back to default routes if no pair-specific found
    if not targets and dest_upper in ROUTE_DATABASE:
        targets = ROUTE_DATABASE[dest_upper]["targets"].copy()

    # Apply limit if specified
    if limit and targets:
        targets = targets[:limit]

    return targets, is_pair_specific


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
    Get list of origins that have pair-specific route configurations.

    Returns:
        Sorted list of unique origin airport codes from PAIR_ROUTES
    """
    origins = set(pair[0] for pair in PAIR_ROUTES.keys())
    return sorted(origins)


def list_supported_pairs() -> list[tuple[str, str]]:
    """
    Get list of all A→B pairs that have specific route configurations.

    Returns:
        Sorted list of (origin, destination) tuples
    """
    return sorted(PAIR_ROUTES.keys())


def get_pair_destinations(origin: str) -> list[str]:
    """
    Get list of destinations that have pair-specific routes from a given origin.

    Args:
        origin: Origin airport code

    Returns:
        List of destination codes with custom routes from this origin
    """
    origin_upper = origin.upper().strip()
    destinations = [pair[1] for pair in PAIR_ROUTES.keys() if pair[0] == origin_upper]
    return sorted(destinations)


# Legacy alias
def get_origin_specific_destinations(origin: str) -> list[str]:
    """Deprecated: Use get_pair_destinations instead."""
    return get_pair_destinations(origin)


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
        # Origin and destination provided - show pair-specific info
        origin = sys.argv[1].upper()
        dest = sys.argv[2].upper()
        targets, is_pair_specific = get_target_routes(dest, origin)

        print(f"\n{origin} → {dest} Route Information:")
        if is_pair_specific:
            print(f"  [PAIR-SPECIFIC ROUTES]")
        else:
            print(f"  [DEFAULT ROUTES - no {origin}→{dest} pair config]")
        print(f"  C Destinations: {', '.join(targets) if targets else 'None found'}")

        info = get_destination_info(dest)
        if info:
            print(f"  {dest} Hub for: {', '.join(info.get('hub_for', [])) or 'N/A'}")
            print(f"  {dest} Notes: {info.get('notes', 'N/A')}")

    elif len(sys.argv) > 1:
        dest = sys.argv[1].upper()
        info = get_destination_info(dest)
        if info:
            print(f"\n{dest} Default Route Information:")
            print(f"  Default C targets: {', '.join(info.get('targets', []))}")
            print(f"  Hub for: {', '.join(info.get('hub_for', [])) or 'N/A'}")
            print(f"  Notes: {info.get('notes', 'N/A')}")

            # Show which A→B pairs exist for this destination
            pairs_to_dest = [(a, b) for (a, b) in PAIR_ROUTES.keys() if b == dest]
            if pairs_to_dest:
                print(f"\n  Pair-specific routes to {dest}:")
                for orig, _ in sorted(pairs_to_dest):
                    targets = PAIR_ROUTES[(orig, dest)]
                    print(f"    {orig}→{dest}: {', '.join(targets[:4])}...")
        else:
            print(f"\n{dest} not found in default database.")
            # Check if it exists in any pairs
            pairs_to_dest = [(a, b) for (a, b) in PAIR_ROUTES.keys() if b == dest]
            if pairs_to_dest:
                print(f"\nHowever, pair-specific routes exist:")
                for orig, _ in sorted(pairs_to_dest):
                    targets = PAIR_ROUTES[(orig, dest)]
                    print(f"  {orig}→{dest}: {', '.join(targets)}")
            print(f"\nSupported destinations: {', '.join(list_supported_destinations())}")
    else:
        print("\nUsage:")
        print("  python -m src.data.route_database <destination>")
        print("  python -m src.data.route_database <origin> <destination>")

        print("\n" + "=" * 60)
        print("DEFAULT ROUTES (by destination B)")
        print("=" * 60)
        for code in list_supported_destinations():
            info = ROUTE_DATABASE[code]
            targets = info["targets"][:3]
            print(f"  {code}: → {', '.join(targets)}...")

        print("\n" + "=" * 60)
        print("PAIR-SPECIFIC ROUTES (A→B pairs)")
        print("=" * 60)
        for origin in list_supported_origins():
            dests = get_pair_destinations(origin)
            print(f"  {origin} →")
            for dest in dests:
                targets = PAIR_ROUTES[(origin, dest)][:3]
                print(f"      {dest}: {', '.join(targets)}...")
