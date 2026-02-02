"""
Flight data models for the flight-arbitrage system.
"""

from .flight import (
    FlightSource,
    DealType,
    FlightResult,
    extract_price,
    normalize_google_flight,
    normalize_skiplagged_flight,
    normalize_orchestrator_flight,
    normalize_flight,
)

__all__ = [
    'FlightSource',
    'DealType',
    'FlightResult',
    'extract_price',
    'normalize_google_flight',
    'normalize_skiplagged_flight',
    'normalize_orchestrator_flight',
    'normalize_flight',
]
