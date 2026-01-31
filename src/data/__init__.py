"""Data modules for flight arbitrage."""
from .route_database import (
    ROUTE_DATABASE,
    get_target_routes,
    get_destination_info,
    list_supported_destinations,
    search_by_hub_airline,
)

__all__ = [
    "ROUTE_DATABASE",
    "get_target_routes",
    "get_destination_info",
    "list_supported_destinations",
    "search_by_hub_airline",
]
