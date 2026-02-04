"""
Geo Location Arbitrage Module

Search flights from multiple geographic locations to find price differences.
Airlines often price differently based on Point of Sale (POS) location.

Two search modes:
1. Simple: search_with_geo_arbitrage() - One route across multiple locations
2. Hybrid: run_hybrid_geo_search() - Full parallel search + geo on discovered routes
"""

from src.geo.proxy_config import ProxyConfig, LOCATIONS, get_proxy_for_location
from src.geo.currency import CurrencyConverter, normalize_price
from src.geo.geo_search import (
    GeoArbitrageSearch,
    search_with_geo_arbitrage,
    run_hybrid_geo_search,
    MultiRouteGeoResult,
)

__all__ = [
    "ProxyConfig",
    "LOCATIONS",
    "get_proxy_for_location",
    "CurrencyConverter",
    "normalize_price",
    "GeoArbitrageSearch",
    "search_with_geo_arbitrage",
    "run_hybrid_geo_search",
    "MultiRouteGeoResult",
]
