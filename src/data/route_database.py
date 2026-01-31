"""
Route Database for Skiplagging Searches
========================================

This module contains mappings of destinations (B) to potential "beyond" cities (C)
that frequently have B as a layover when flying from East Coast origins.

The key insight: If you want to fly to city B, search for flights to cities C
that are BEYOND B geographically. Airlines often route through B as a hub.

Usage:
    from src.data.route_database import get_target_routes, ROUTE_DATABASE

    # Get suggested routes for a destination
    targets = get_target_routes("DEN")  # Returns ['LAX', 'SFO', 'SEA', ...]
"""

# =============================================================================
# ROUTE DATABASE
# =============================================================================
# Key = Your true destination (B) - where you actually want to go
# Value = Cities BEYOND B (C destinations) that often have B as a layover
#
# Organized by geographic region and hub status
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

def get_target_routes(destination: str, limit: int = None) -> list[str]:
    """
    Get suggested target routes (C destinations) for a given destination (B).

    Args:
        destination: Airport code of your true destination (e.g., "DEN")
        limit: Optional limit on number of targets to return

    Returns:
        List of airport codes to search (cities beyond destination)
    """
    dest_upper = destination.upper().strip()

    if dest_upper in ROUTE_DATABASE:
        targets = ROUTE_DATABASE[dest_upper]["targets"]
        if limit:
            return targets[:limit]
        return targets

    return []


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
    Get list of all supported destination codes.

    Returns:
        Sorted list of airport codes in the database
    """
    return sorted(ROUTE_DATABASE.keys())


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

    if len(sys.argv) > 1:
        dest = sys.argv[1]
        info = get_destination_info(dest)
        if info:
            print(f"\n{dest.upper()} Route Information:")
            print(f"  Targets: {', '.join(info.get('targets', []))}")
            print(f"  Hub for: {', '.join(info.get('hub_for', [])) or 'N/A'}")
            print(f"  Notes: {info.get('notes', 'N/A')}")
        else:
            print(f"\n{dest.upper()} not found in database.")
            print(f"\nSupported destinations: {', '.join(list_supported_destinations())}")
    else:
        print("\nSupported Destinations:")
        print("-" * 40)
        for code in list_supported_destinations():
            info = ROUTE_DATABASE[code]
            targets = info["targets"][:3]
            print(f"  {code}: {', '.join(targets)}...")
