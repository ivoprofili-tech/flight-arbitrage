"""
Unified flight data model for the flight-arbitrage system.

This module provides a normalized data structure for flight results
from multiple sources (Google Flights, Skiplagged, Hidden City searches).
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any
import re


class FlightSource(Enum):
    """Enum representing the source of a flight result."""
    GOOGLE_FLIGHTS = "google_flights"
    SKIPLAGGED = "skiplagged"
    HIDDEN_CITY = "hidden_city"


class DealType(Enum):
    """Enum representing the type of deal found."""
    DIRECT = "direct"                       # Standard direct booking
    SKIPLAGGED_DEAL = "skiplagged_deal"     # Skiplagged marked as deal
    HIDDEN_CITY = "hidden_city"             # Confirmed hidden city opportunity
    POTENTIAL_HIDDEN_CITY = "potential_hidden_city"  # Possible hidden city (unconfirmed)
    NOT_TARGET_LAYOVER = "not_target_layover"  # Has layover but not target city


@dataclass
class FlightResult:
    """
    Unified flight result structure that normalizes data from all sources.

    This dataclass consolidates flight information from Google Flights,
    Skiplagged, and Hidden City orchestrator searches into a single format.
    """

    # Core flight information (common to all sources)
    airline: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: str
    price: str

    # Normalized price for sorting/comparison
    price_numeric: int = 0

    # Source tracking
    source: FlightSource = FlightSource.GOOGLE_FLIGHTS

    # Layover information (primarily from Google Flights)
    layovers: List[str] = field(default_factory=list)

    # Deal classification
    deal_type: DealType = DealType.DIRECT

    # Hidden city specific fields
    final_destination: Optional[str] = None      # The C destination (where ticket is booked to)
    hidden_city_target: Optional[str] = None     # The B destination (where you actually get off)
    search_route: Optional[str] = None           # The route searched (e.g., "GRU → MIA")
    confirmed_layover: bool = False              # Whether target layover was confirmed

    # Skiplagged specific fields
    is_skiplagged_deal: bool = False             # Marked as deal on Skiplagged
    savings: Optional[str] = None                # Savings amount (e.g., "$41 off")
    original_price: Optional[str] = None         # Original price before discount

    # Route information
    origin: Optional[str] = None                 # Origin airport code
    destination: Optional[str] = None            # Destination airport code

    # Deduplication key (generated)
    _dedup_key: Optional[str] = field(default=None, repr=False)

    def __post_init__(self):
        """Generate deduplication key after initialization."""
        if self._dedup_key is None:
            self._dedup_key = self._generate_dedup_key()

    def _generate_dedup_key(self) -> str:
        """
        Generate a unique key for deduplication.

        Uses airline, departure time, arrival time, and price to identify
        the same flight across different sources.
        """
        # Normalize times for comparison (remove spaces, lowercase)
        dep = self.departure_time.lower().replace(" ", "").replace(".", "")
        arr = self.arrival_time.lower().replace(" ", "").replace(".", "")

        # Normalize airline name
        airline = self.airline.lower().strip()

        # Use price_numeric if available, otherwise extract from price string
        price = self.price_numeric if self.price_numeric > 0 else extract_price(self.price)

        return f"{airline}|{dep}|{arr}|{price}"

    @property
    def dedup_key(self) -> str:
        """Get the deduplication key."""
        return self._dedup_key or self._generate_dedup_key()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling enums properly."""
        result = asdict(self)
        result['source'] = self.source.value
        result['deal_type'] = self.deal_type.value
        # Remove internal fields
        result.pop('_dedup_key', None)
        return result

    def to_display_dict(self) -> Dict[str, Any]:
        """
        Convert to a simplified dictionary for display purposes.
        Only includes non-None fields relevant to the source.
        """
        base = {
            'airline': self.airline,
            'departure_time': self.departure_time,
            'arrival_time': self.arrival_time,
            'duration': self.duration,
            'stops': self.stops,
            'price': self.price,
            'source': self.source.value,
        }

        if self.layovers:
            base['layovers'] = self.layovers

        if self.deal_type != DealType.DIRECT:
            base['deal_type'] = self.deal_type.value

        # Hidden city fields
        if self.source == FlightSource.HIDDEN_CITY:
            if self.final_destination:
                base['final_destination'] = self.final_destination
            if self.hidden_city_target:
                base['hidden_city_target'] = self.hidden_city_target
            if self.search_route:
                base['search_route'] = self.search_route
            base['confirmed_layover'] = self.confirmed_layover

        # Skiplagged fields
        if self.source == FlightSource.SKIPLAGGED:
            if self.is_skiplagged_deal:
                base['is_skiplagged_deal'] = True
            if self.savings:
                base['savings'] = self.savings
            if self.original_price:
                base['original_price'] = self.original_price

        return base


def extract_price(price_str: str) -> int:
    """
    Extract numeric price from a price string.

    Handles various formats:
    - "$299"
    - "$1,299"
    - "USD 299"
    - "299"

    Args:
        price_str: Price string to parse

    Returns:
        Integer price value, or 0 if parsing fails
    """
    if not price_str:
        return 0

    # Remove currency symbols and whitespace
    cleaned = re.sub(r'[^\d,.]', '', str(price_str))

    # Remove commas (thousand separators)
    cleaned = cleaned.replace(',', '')

    # Handle decimal prices (take integer part)
    if '.' in cleaned:
        cleaned = cleaned.split('.')[0]

    try:
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0


def normalize_google_flight(
    flight_data: Dict[str, Any],
    origin: Optional[str] = None,
    destination: Optional[str] = None
) -> FlightResult:
    """
    Normalize a flight result from Google Flights scraper.

    Expected input format:
    {
        'airline': 'United',
        'departure_time': '12:59 PM',
        'arrival_time': '6:50 PM',
        'duration': '5h 51m',
        'stops': '1 stop',
        'price': '$299',
        'layovers': ['LAX', 'DEN']  # Optional
    }

    Args:
        flight_data: Raw flight data from Google Flights scraper
        origin: Origin airport code
        destination: Destination airport code

    Returns:
        Normalized FlightResult object
    """
    layovers = flight_data.get('layovers', [])
    if isinstance(layovers, str):
        layovers = [layovers] if layovers else []

    price_str = flight_data.get('price', '$0')

    return FlightResult(
        airline=flight_data.get('airline', 'Unknown'),
        departure_time=flight_data.get('departure_time', ''),
        arrival_time=flight_data.get('arrival_time', ''),
        duration=flight_data.get('duration', ''),
        stops=flight_data.get('stops', ''),
        price=price_str,
        price_numeric=extract_price(price_str),
        source=FlightSource.GOOGLE_FLIGHTS,
        layovers=layovers,
        deal_type=DealType.DIRECT,
        origin=origin,
        destination=destination,
    )


def normalize_skiplagged_flight(
    flight_data: Dict[str, Any],
    origin: Optional[str] = None,
    destination: Optional[str] = None
) -> FlightResult:
    """
    Normalize a flight result from Skiplagged scraper.

    Expected input format:
    {
        'airline': 'JetBlue',
        'departure_time': '6:00am',
        'arrival_time': '9:16pm',
        'duration': '6h',
        'stops': '1 stop',
        'price': '$209',
        'source': 'Skiplagged',
        'skiplagged_deal': True,        # Optional
        'savings': '$41 off',           # Optional
        'original_price': '$250'        # Optional
    }

    Args:
        flight_data: Raw flight data from Skiplagged scraper
        origin: Origin airport code
        destination: Destination airport code

    Returns:
        Normalized FlightResult object
    """
    is_deal = flight_data.get('skiplagged_deal', False)
    price_str = flight_data.get('price', '$0')

    # Determine deal type
    deal_type = DealType.SKIPLAGGED_DEAL if is_deal else DealType.DIRECT

    return FlightResult(
        airline=flight_data.get('airline', 'Unknown'),
        departure_time=flight_data.get('departure_time', ''),
        arrival_time=flight_data.get('arrival_time', ''),
        duration=flight_data.get('duration', ''),
        stops=flight_data.get('stops', ''),
        price=price_str,
        price_numeric=extract_price(price_str),
        source=FlightSource.SKIPLAGGED,
        layovers=[],  # Skiplagged doesn't provide layover details
        deal_type=deal_type,
        is_skiplagged_deal=is_deal,
        savings=flight_data.get('savings'),
        original_price=flight_data.get('original_price'),
        origin=origin,
        destination=destination,
    )


def normalize_orchestrator_flight(
    flight_data: Dict[str, Any],
    origin: Optional[str] = None,
    hidden_city_target: Optional[str] = None
) -> FlightResult:
    """
    Normalize a flight result from the Hidden City orchestrator.

    Expected input format:
    {
        'airline': 'American',
        'departure_time': '8:00 AM',
        'arrival_time': '2:30 PM',
        'duration': '6h 30m',
        'stops': '1 stop',
        'price': '$312',
        'layovers': ['MCO'],
        'final_destination': 'MIA',
        'hidden_city_target': 'MCO',
        'search_route': 'GRU → MIA',
        'deal_type': 'hidden_city',
        'confirmed_layover': True
    }

    Args:
        flight_data: Raw flight data from orchestrator
        origin: Origin airport code
        hidden_city_target: The target layover city (B in A→B→C)

    Returns:
        Normalized FlightResult object
    """
    layovers = flight_data.get('layovers', [])
    if isinstance(layovers, str):
        layovers = [layovers] if layovers else []

    price_str = flight_data.get('price', '$0')

    # Map deal_type string to enum
    deal_type_str = flight_data.get('deal_type', 'direct')
    deal_type_map = {
        'hidden_city': DealType.HIDDEN_CITY,
        'potential_hidden_city': DealType.POTENTIAL_HIDDEN_CITY,
        'not_target_layover': DealType.NOT_TARGET_LAYOVER,
        'direct': DealType.DIRECT,
    }
    deal_type = deal_type_map.get(deal_type_str, DealType.DIRECT)

    return FlightResult(
        airline=flight_data.get('airline', 'Unknown'),
        departure_time=flight_data.get('departure_time', ''),
        arrival_time=flight_data.get('arrival_time', ''),
        duration=flight_data.get('duration', ''),
        stops=flight_data.get('stops', ''),
        price=price_str,
        price_numeric=extract_price(price_str),
        source=FlightSource.HIDDEN_CITY,
        layovers=layovers,
        deal_type=deal_type,
        final_destination=flight_data.get('final_destination'),
        hidden_city_target=hidden_city_target or flight_data.get('hidden_city_target'),
        search_route=flight_data.get('search_route'),
        confirmed_layover=flight_data.get('confirmed_layover', False),
        origin=origin,
        destination=hidden_city_target,  # The actual destination is where you get off
    )


def normalize_flight(
    flight_data: Dict[str, Any],
    source: FlightSource,
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    hidden_city_target: Optional[str] = None
) -> FlightResult:
    """
    Universal normalization function that routes to the appropriate normalizer.

    Args:
        flight_data: Raw flight data from any scraper
        source: The source of the flight data
        origin: Origin airport code
        destination: Destination airport code
        hidden_city_target: For hidden city searches, the target layover city

    Returns:
        Normalized FlightResult object
    """
    if source == FlightSource.GOOGLE_FLIGHTS:
        return normalize_google_flight(flight_data, origin, destination)
    elif source == FlightSource.SKIPLAGGED:
        return normalize_skiplagged_flight(flight_data, origin, destination)
    elif source == FlightSource.HIDDEN_CITY:
        return normalize_orchestrator_flight(flight_data, origin, hidden_city_target)
    else:
        raise ValueError(f"Unknown flight source: {source}")
