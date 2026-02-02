"""
Layover Detection Utilities
============================

Shared utilities for detecting layover cities in flight data.
Used by both the parallel search engine and the standalone orchestrator.
"""

from typing import List, Dict, Any, Set


# =============================================================================
# CITY/AIRPORT MAPPINGS
# =============================================================================

CITY_MAPPINGS = {
    # US Major Hubs
    'LAX': ['LAX', 'Los Angeles', 'LA'],
    'JFK': ['JFK', 'New York', 'NYC', 'Kennedy'],
    'EWR': ['EWR', 'Newark', 'New York', 'NYC'],
    'LGA': ['LGA', 'LaGuardia', 'New York', 'NYC'],
    'ORD': ['ORD', 'Chicago', "O'Hare", 'OHare'],
    'SFO': ['SFO', 'San Francisco', 'SF'],
    'MIA': ['MIA', 'Miami'],
    'FLL': ['FLL', 'Fort Lauderdale', 'Ft Lauderdale'],
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
    'TPA': ['TPA', 'Tampa'],
    'IAH': ['IAH', 'Houston', 'George Bush'],
    'AUS': ['AUS', 'Austin'],
    'SLC': ['SLC', 'Salt Lake City'],
    'DCA': ['DCA', 'Washington', 'DC', 'Reagan'],
    'IAD': ['IAD', 'Dulles', 'Washington', 'DC'],

    # International
    'GRU': ['GRU', 'Sao Paulo', 'Guarulhos', 'São Paulo'],
    'GIG': ['GIG', 'Rio de Janeiro', 'Rio', 'Galeao'],
    'MEX': ['MEX', 'Mexico City', 'CDMX'],
    'YYZ': ['YYZ', 'Toronto'],
    'YVR': ['YVR', 'Vancouver'],
    'LHR': ['LHR', 'London', 'Heathrow'],
    'CDG': ['CDG', 'Paris', 'Charles de Gaulle'],
    'FRA': ['FRA', 'Frankfurt'],
    'NRT': ['NRT', 'Tokyo', 'Narita'],
    'HND': ['HND', 'Tokyo', 'Haneda'],
    'HKG': ['HKG', 'Hong Kong'],
    'SIN': ['SIN', 'Singapore'],
    'DXB': ['DXB', 'Dubai'],
}


def get_city_variants(city: str) -> List[str]:
    """
    Get various name variants for a city to improve matching.

    Args:
        city: City name or airport code

    Returns:
        List of possible variants to search for

    Examples:
        >>> get_city_variants('MCO')
        ['MCO', 'Orlando']
        >>> get_city_variants('JFK')
        ['JFK', 'New York', 'NYC', 'Kennedy']
    """
    city_upper = city.upper().strip()

    # If it's a known airport code, return all variants
    if city_upper in CITY_MAPPINGS:
        return CITY_MAPPINGS[city_upper]

    # Check if the city name matches any mapping
    city_lower = city.lower().strip()
    for code, variants in CITY_MAPPINGS.items():
        for variant in variants:
            if variant.lower() == city_lower:
                return CITY_MAPPINGS[code]

    # Default: return the city and common variations
    return [city, city.upper(), city.lower(), city.title()]


def get_city_variants_set(city: str) -> Set[str]:
    """
    Get city variants as a set for faster lookups.

    Args:
        city: City name or airport code

    Returns:
        Set of uppercase variants for matching
    """
    variants = get_city_variants(city)
    return {v.upper().strip() for v in variants}


def check_layovers_list(layovers: List[str], city_variants: List[str]) -> bool:
    """
    Check if any city variant appears in the layovers list.

    This is the preferred method when the scraper has extracted explicit
    layover airport codes from the flight details.

    Args:
        layovers: List of airport codes from the flight (e.g., ['LAX', 'DEN'])
        city_variants: List of city name/code variants to search for

    Returns:
        True if a layover at the target city is detected

    Examples:
        >>> check_layovers_list(['ATL', 'MCO'], ['MCO', 'Orlando'])
        True
        >>> check_layovers_list(['ATL', 'DEN'], ['MCO', 'Orlando'])
        False
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


def check_layover_in_text(flight_text: str, city_variants: List[str]) -> bool:
    """
    Check if any city variant appears in the flight text.

    This is a fallback method when explicit layover data is not available.

    Args:
        flight_text: Combined flight information text
        city_variants: List of city name variants to search for

    Returns:
        True if a layover at the target city is detected

    Examples:
        >>> check_layover_in_text('1 stop via Orlando', ['MCO', 'Orlando'])
        True
    """
    flight_lower = flight_text.lower()

    for variant in city_variants:
        if variant.lower() in flight_lower:
            return True

    return False


def get_flight_text(flight: Dict[str, Any]) -> str:
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


def has_target_layover(
    flight: Dict[str, Any],
    target_city: str,
    city_variants: List[str] = None
) -> bool:
    """
    Check if a flight has the target city as a layover.

    This function combines multiple detection strategies:
    1. Check explicit layovers list (preferred)
    2. Fall back to text search if no layovers extracted

    Args:
        flight: Flight dictionary with 'layovers' and other fields
        target_city: The city to look for as a layover
        city_variants: Optional pre-computed city variants

    Returns:
        True if the target city appears to be a layover

    Examples:
        >>> flight = {'layovers': ['MCO'], 'stops': '1 stop'}
        >>> has_target_layover(flight, 'MCO')
        True
    """
    if city_variants is None:
        city_variants = get_city_variants(target_city)

    # Get layovers list from flight
    layovers = flight.get('layovers', [])
    if isinstance(layovers, str):
        layovers = [layovers] if layovers else []

    # Strategy 1: Check explicit layovers list
    if layovers:
        return check_layovers_list(layovers, city_variants)

    # Strategy 2: Fall back to text search
    flight_text = get_flight_text(flight)
    return check_layover_in_text(flight_text, city_variants)


def is_connecting_flight(flight: Dict[str, Any]) -> bool:
    """
    Check if a flight is a connecting flight (has stops).

    Args:
        flight: Flight dictionary with 'stops' field

    Returns:
        True if the flight has one or more stops
    """
    stops = flight.get('stops', '').lower()

    # Nonstop flights
    if 'nonstop' in stops or 'non-stop' in stops:
        return False

    # Has stops
    if 'stop' in stops:
        return True

    # Unknown - assume not connecting
    return False


def parse_price(price_str: str) -> int:
    """
    Parse a price string to an integer for sorting.

    Args:
        price_str: Price string like "$299", "US$1,234", etc.

    Returns:
        Integer price value, or 999999 if parsing fails

    Examples:
        >>> parse_price('$299')
        299
        >>> parse_price('$1,234')
        1234
    """
    try:
        # Remove currency symbols, commas, spaces
        cleaned = ''.join(c for c in str(price_str) if c.isdigit())
        return int(cleaned) if cleaned else 999999
    except:
        return 999999
