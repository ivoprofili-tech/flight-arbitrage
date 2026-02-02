"""Data modules for flight arbitrage."""
from .route_database import (
    ROUTE_DATABASE,
    PAIR_ROUTES,
    get_target_routes,
    get_destination_info,
    list_supported_destinations,
    list_supported_origins,
    list_supported_pairs,
    get_pair_destinations,
    get_origin_specific_destinations,  # Legacy alias
    search_by_hub_airline,
)

__all__ = [
    "ROUTE_DATABASE",
    "PAIR_ROUTES",
    "get_target_routes",
    "get_destination_info",
    "list_supported_destinations",
    "list_supported_origins",
    "list_supported_pairs",
    "get_pair_destinations",
    "get_origin_specific_destinations",
    "search_by_hub_airline",
]
