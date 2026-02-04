"""
Geo Location Arbitrage Module

Search flights from multiple geographic locations to find price differences.
Airlines often price differently based on Point of Sale (POS) location.
"""

from src.geo.proxy_config import ProxyConfig, LOCATIONS, get_proxy_for_location
from src.geo.currency import CurrencyConverter, normalize_price
from src.geo.geo_search import GeoArbitrageSearch, search_with_geo_arbitrage

__all__ = [
    "ProxyConfig",
    "LOCATIONS",
    "get_proxy_for_location",
    "CurrencyConverter",
    "normalize_price",
    "GeoArbitrageSearch",
    "search_with_geo_arbitrage",
]
