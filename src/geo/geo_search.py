"""
Geo Arbitrage Search Orchestrator

Runs parallel flight searches from multiple geographic locations
and compares prices to find the best Point of Sale (POS).

Supports two modes:
1. Single route search - search one A→B route from multiple locations
2. Hybrid search - first run full parallel search, then geo-compare direct + hidden city routes

Usage:
    # Simple single route
    results = await search_with_geo_arbitrage(
        origin="GRU",
        destination="MCO",
        departure_date="2026-03-15",
        locations=["BR", "US", "CO"],
    )

    # Hybrid: full search then geo arbitrage on discovered routes
    results = await run_hybrid_geo_search(
        origin="GRU",
        destination="MCO",
        departure_date="2026-03-15",
        locations=["BR", "US", "CO"],
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from src.geo.proxy_config import (
    get_proxy_for_location,
    get_location_config,
    LOCATIONS,
    ProxyConfig,
    LocationConfig,
)
from src.geo.currency import (
    CurrencyConverter,
    get_converter,
    ensure_rates_loaded,
    parse_price,
)
from src.scraper.google_flights_serpapi import search_google_flights
from src.scraper.skiplagged import search_skiplagged_flights

logger = logging.getLogger(__name__)


class SearchSource(Enum):
    GOOGLE_FLIGHTS = "google_flights"
    SKIPLAGGED = "skiplagged"


@dataclass
class GeoFlightResult:
    """A flight result with geo-location context."""
    # Flight details
    airline: str
    departure_time: str
    arrival_time: str
    duration: str
    stops: str
    price_original: str        # Original price string (e.g., "R$1.200")
    price_usd: float           # Normalized to USD
    currency: str              # Detected/expected currency

    # Geo context
    location: str              # Country code (BR, US, CO, etc.)
    location_name: str         # Human-readable (Brazil, United States, etc.)
    source: SearchSource       # google_flights or skiplagged

    # Additional details
    layovers: List[str] = field(default_factory=list)
    flight_numbers: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "airline": self.airline,
            "flight_numbers": self.flight_numbers,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "duration": self.duration,
            "stops": self.stops,
            "price_original": self.price_original,
            "price_usd": round(self.price_usd, 2),
            "currency": self.currency,
            "location": self.location,
            "location_name": self.location_name,
            "source": self.source.value,
            "layovers": self.layovers,
        }


@dataclass
class LocationSearchResult:
    """Results from a single location search."""
    location: str
    location_name: str
    status: str  # "success", "error", "no_proxy"
    flights: List[GeoFlightResult]
    search_time_seconds: float
    error_message: Optional[str] = None
    best_price_usd: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "location_name": self.location_name,
            "status": self.status,
            "flights_found": len(self.flights),
            "search_time_seconds": round(self.search_time_seconds, 2),
            "error_message": self.error_message,
            "best_price_usd": round(self.best_price_usd, 2) if self.best_price_usd else None,
            "flights": [f.to_dict() for f in self.flights],
        }


@dataclass
class GeoArbitrageResult:
    """Complete geo arbitrage search results."""
    search_params: Dict[str, str]
    timestamp: datetime
    total_search_time_seconds: float

    # Results by location
    location_results: Dict[str, LocationSearchResult]

    # Best deals
    best_overall: Optional[GeoFlightResult] = None
    best_by_location: Dict[str, GeoFlightResult] = field(default_factory=dict)

    # Savings analysis
    price_comparison: Dict[str, float] = field(default_factory=dict)  # location -> best price USD
    best_location: Optional[str] = None
    potential_savings_usd: float = 0.0
    potential_savings_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_params": self.search_params,
            "timestamp": self.timestamp.isoformat(),
            "total_search_time_seconds": round(self.total_search_time_seconds, 2),
            "summary": {
                "locations_searched": list(self.location_results.keys()),
                "best_location": self.best_location,
                "best_price_usd": round(self.best_overall.price_usd, 2) if self.best_overall else None,
                "potential_savings_usd": round(self.potential_savings_usd, 2),
                "potential_savings_pct": round(self.potential_savings_pct, 1),
                "price_by_location": {
                    loc: round(price, 2) for loc, price in self.price_comparison.items()
                },
            },
            "best_overall": self.best_overall.to_dict() if self.best_overall else None,
            "best_by_location": {
                loc: flight.to_dict() for loc, flight in self.best_by_location.items()
            },
            "location_results": {
                loc: result.to_dict() for loc, result in self.location_results.items()
            },
        }


class GeoArbitrageSearch:
    """
    Orchestrates flight searches across multiple geographic locations.

    Runs parallel searches using proxies for different countries,
    normalizes prices to USD, and identifies the best Point of Sale.
    """

    def __init__(
        self,
        locations: List[str] = None,
        max_concurrent: int = 3,
        headless: bool = True,
        sources: List[str] = None,
    ):
        """
        Initialize the geo arbitrage search.

        Args:
            locations: Country codes to search from (default: all configured)
            max_concurrent: Max concurrent location searches
            headless: Run browsers in headless mode
            sources: Which sources to search (default: google_flights only for geo)
        """
        self.locations = locations or list(LOCATIONS.keys())
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.sources = sources or ["google_flights"]  # Default to GF only for geo
        self.converter: Optional[CurrencyConverter] = None

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = None,
    ) -> GeoArbitrageResult:
        """
        Run geo arbitrage search across all configured locations.

        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Optional return date

        Returns:
            GeoArbitrageResult with comparative pricing
        """
        start_time = datetime.now()

        # Ensure exchange rates are loaded
        self.converter = await ensure_rates_loaded()

        logger.info(f"Starting geo arbitrage search: {origin} → {destination}")
        logger.info(f"Locations: {', '.join(self.locations)}")

        # Create search tasks for each location
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def search_location(location: str) -> LocationSearchResult:
            async with semaphore:
                return await self._search_single_location(
                    location=location,
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                )

        # Run all location searches in parallel
        tasks = [search_location(loc) for loc in self.locations]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        location_results: Dict[str, LocationSearchResult] = {}
        for loc, result in zip(self.locations, results):
            if isinstance(result, Exception):
                logger.error(f"Search failed for {loc}: {result}")
                location_results[loc] = LocationSearchResult(
                    location=loc,
                    location_name=LOCATIONS.get(loc, LocationConfig(loc, loc, "", "", "", "", "")).name,
                    status="error",
                    flights=[],
                    search_time_seconds=0,
                    error_message=str(result),
                )
            else:
                location_results[loc] = result

        # Calculate total time
        total_time = (datetime.now() - start_time).total_seconds()

        # Analyze results
        return self._analyze_results(
            location_results=location_results,
            search_params={
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
            },
            total_time=total_time,
        )

    async def _search_single_location(
        self,
        location: str,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = None,
    ) -> LocationSearchResult:
        """Search from a single location."""
        start_time = datetime.now()
        location_config = get_location_config(location)

        if not location_config:
            return LocationSearchResult(
                location=location,
                location_name=location,
                status="error",
                flights=[],
                search_time_seconds=0,
                error_message=f"Unknown location: {location}",
            )

        # SerpApi uses the gl parameter for geo-targeting -- no proxy needed
        # for Google Flights. Proxy is only needed for Skiplagged.
        proxy_config = get_proxy_for_location(location)
        proxy_dict = proxy_config.to_playwright_proxy() if proxy_config else None

        flights: List[GeoFlightResult] = []

        try:
            # Search Google Flights if enabled
            if "google_flights" in self.sources:
                gf_flights = await search_google_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    geo_location=location,
                    currency=location_config.currency,
                )

                # Convert to GeoFlightResult
                for f in gf_flights:
                    if "error" in f:
                        continue

                    price_str = f.get("price", "$0")
                    amount, currency = parse_price(price_str)

                    # SerpApi returns prices in the requested currency but the
                    # price string may still have "$" for some currencies.
                    # Override with the location's expected currency.
                    if currency == "USD" and location_config.currency != "USD":
                        currency = location_config.currency

                    price_usd = self.converter.to_usd(amount, currency)

                    # Skip flights with zero/missing prices
                    if amount <= 0 or price_usd <= 0:
                        continue

                    flights.append(GeoFlightResult(
                        airline=f.get("airline", "Unknown"),
                        departure_time=f.get("departure_time", ""),
                        arrival_time=f.get("arrival_time", ""),
                        duration=f.get("duration", ""),
                        stops=f.get("stops", ""),
                        price_original=price_str,
                        price_usd=price_usd,
                        currency=currency,
                        location=location,
                        location_name=location_config.name,
                        source=SearchSource.GOOGLE_FLIGHTS,
                        layovers=f.get("layovers", []),
                        flight_numbers=f.get("flight_numbers", ""),
                    ))

            # Search Skiplagged if enabled
            if "skiplagged" in self.sources:
                sl_flights = await search_skiplagged_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    headless=self.headless,
                    proxy=proxy_dict,
                    locale=location_config.locale,
                    language=location_config.language,
                    timezone=location_config.timezone,
                    geo_location=location,
                )

                for f in sl_flights:
                    if "error" in f:
                        continue

                    price_str = f.get("price", "$0")
                    amount, currency = parse_price(price_str)
                    price_usd = self.converter.to_usd(amount, currency)

                    flights.append(GeoFlightResult(
                        airline=f.get("airline", "Unknown"),
                        departure_time=f.get("departure_time", ""),
                        arrival_time=f.get("arrival_time", ""),
                        duration=f.get("duration", ""),
                        stops=f.get("stops", ""),
                        price_original=price_str,
                        price_usd=price_usd,
                        currency=currency,
                        location=location,
                        location_name=location_config.name,
                        source=SearchSource.SKIPLAGGED,
                    ))

            search_time = (datetime.now() - start_time).total_seconds()

            # Find best price
            best_price = min((f.price_usd for f in flights), default=None)

            logger.info(f"[{location}] Found {len(flights)} flights, best: ${best_price:.2f}" if best_price else f"[{location}] Found {len(flights)} flights")

            return LocationSearchResult(
                location=location,
                location_name=location_config.name,
                status="success" if flights else "no_flights",
                flights=flights,
                search_time_seconds=search_time,
                best_price_usd=best_price,
            )

        except Exception as e:
            logger.error(f"Error searching from {location}: {e}")
            search_time = (datetime.now() - start_time).total_seconds()

            return LocationSearchResult(
                location=location,
                location_name=location_config.name,
                status="error",
                flights=[],
                search_time_seconds=search_time,
                error_message=str(e),
            )

    def _analyze_results(
        self,
        location_results: Dict[str, LocationSearchResult],
        search_params: Dict[str, str],
        total_time: float,
    ) -> GeoArbitrageResult:
        """Analyze results across locations and calculate savings."""

        # Find best flight per location
        best_by_location: Dict[str, GeoFlightResult] = {}
        price_comparison: Dict[str, float] = {}

        for loc, result in location_results.items():
            if result.flights:
                best_flight = min(result.flights, key=lambda f: f.price_usd)
                best_by_location[loc] = best_flight
                price_comparison[loc] = best_flight.price_usd

        # Find overall best
        best_overall = None
        if best_by_location:
            best_overall = min(best_by_location.values(), key=lambda f: f.price_usd)

        # Calculate potential savings
        best_location = None
        potential_savings_usd = 0.0
        potential_savings_pct = 0.0

        if price_comparison:
            best_location = min(price_comparison, key=price_comparison.get)
            worst_price = max(price_comparison.values())
            best_price = min(price_comparison.values())

            if worst_price > best_price:
                potential_savings_usd = worst_price - best_price
                potential_savings_pct = (potential_savings_usd / worst_price) * 100

        return GeoArbitrageResult(
            search_params=search_params,
            timestamp=datetime.now(),
            total_search_time_seconds=total_time,
            location_results=location_results,
            best_overall=best_overall,
            best_by_location=best_by_location,
            price_comparison=price_comparison,
            best_location=best_location,
            potential_savings_usd=potential_savings_usd,
            potential_savings_pct=potential_savings_pct,
        )


async def search_with_geo_arbitrage(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    locations: List[str] = None,
    max_concurrent: int = 3,
    headless: bool = True,
    sources: List[str] = None,
) -> GeoArbitrageResult:
    """
    Convenience function for geo arbitrage search.

    Args:
        origin: Origin airport code
        destination: Destination airport code
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Optional return date
        locations: Country codes to search from (default: all)
        max_concurrent: Max concurrent searches
        headless: Run browsers headless
        sources: Sources to search (default: google_flights)

    Returns:
        GeoArbitrageResult with price comparison

    Example:
        results = await search_with_geo_arbitrage(
            origin="GRU",
            destination="MCO",
            departure_date="2026-03-15",
            locations=["BR", "US", "CO"],
        )

        print(f"Best location: {results.best_location}")
        print(f"Best price: ${results.best_overall.price_usd}")
        print(f"Potential savings: ${results.potential_savings_usd}")
    """
    search = GeoArbitrageSearch(
        locations=locations,
        max_concurrent=max_concurrent,
        headless=headless,
        sources=sources,
    )

    return await search.search(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
    )


# =============================================================================
# HYBRID GEO SEARCH - Full parallel search + geo arbitrage on discovered routes
# =============================================================================

@dataclass
class RouteInfo:
    """Information about a route to geo-search."""
    origin: str
    destination: str
    route_type: str  # "direct" or "hidden_city"
    hidden_city_exit: Optional[str] = None  # Exit airport for hidden city
    original_price: Optional[float] = None  # Price found in initial search


@dataclass
class MultiRouteGeoResult:
    """Results from searching multiple routes across locations."""
    # Search parameters
    primary_origin: str
    primary_destination: str
    departure_date: str
    timestamp: datetime
    total_search_time_seconds: float

    # Phase 1: Initial parallel search results
    initial_search_time_seconds: float
    direct_route_best_price: Optional[float] = None
    hidden_city_routes_found: List[RouteInfo] = field(default_factory=list)

    # Phase 2: Geo arbitrage results by route
    # Key: "origin-destination" (e.g., "GRU-MCO" or "GRU-MIA" for hidden city)
    route_results: Dict[str, GeoArbitrageResult] = field(default_factory=dict)

    # Overall best deals
    best_direct_deal: Optional[Dict[str, Any]] = None  # Best direct route + location
    best_hidden_city_deals: List[Dict[str, Any]] = field(default_factory=list)  # Best HC by route

    # Summary
    total_routes_searched: int = 0
    total_potential_savings_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_params": {
                "primary_origin": self.primary_origin,
                "primary_destination": self.primary_destination,
                "departure_date": self.departure_date,
            },
            "timestamp": self.timestamp.isoformat(),
            "total_search_time_seconds": round(self.total_search_time_seconds, 2),
            "initial_search_time_seconds": round(self.initial_search_time_seconds, 2),
            "summary": {
                "direct_route_best_price": round(self.direct_route_best_price, 2) if self.direct_route_best_price else None,
                "hidden_city_routes_found": len(self.hidden_city_routes_found),
                "total_routes_searched": self.total_routes_searched,
                "total_potential_savings_usd": round(self.total_potential_savings_usd, 2),
            },
            "hidden_city_routes": [
                {
                    "route": f"{r.origin}-{r.destination}",
                    "exit_at": r.hidden_city_exit,
                    "original_price": r.original_price,
                }
                for r in self.hidden_city_routes_found
            ],
            "best_direct_deal": self.best_direct_deal,
            "best_hidden_city_deals": self.best_hidden_city_deals,
            "route_results": {
                route: result.to_dict() for route, result in self.route_results.items()
            },
        }


def extract_hidden_city_routes(parallel_search_results) -> List[RouteInfo]:
    """
    Extract hidden city routes that have deals from parallel search results.

    Args:
        parallel_search_results: Results from ParallelFlightSearch.search_all()

    Returns:
        List of RouteInfo for hidden city routes worth geo-searching
    """
    hidden_city_routes = []

    # Get all hidden city flights from results
    for flight in parallel_search_results.all_flights:
        if flight.deal_type.value == "hidden_city" and flight.hidden_city_target:
            # The search_route is like "GRU→MIA" - parse it
            if "→" in flight.search_route:
                parts = flight.search_route.split("→")
                if len(parts) == 2:
                    origin = parts[0].strip()
                    final_dest = parts[1].strip()

                    route_info = RouteInfo(
                        origin=origin,
                        destination=final_dest,
                        route_type="hidden_city",
                        hidden_city_exit=flight.hidden_city_target,
                        original_price=flight.price_numeric,
                    )

                    # Avoid duplicates (same origin-destination pair)
                    route_key = f"{origin}-{final_dest}"
                    existing_keys = [f"{r.origin}-{r.destination}" for r in hidden_city_routes]
                    if route_key not in existing_keys:
                        hidden_city_routes.append(route_info)

    return hidden_city_routes


async def run_hybrid_geo_search(
    origin: str,
    destination: str,
    departure_date: str,
    locations: List[str] = None,
    max_concurrent: int = 3,
    headless: bool = True,
    initial_search_sources: List[str] = None,
    initial_search_max_concurrent: int = 2,
    initial_search_quick: bool = False,
) -> MultiRouteGeoResult:
    """
    Run hybrid geo search: full parallel search first, then geo arbitrage on discovered routes.

    This is more efficient than running full searches from each location because:
    1. First discover which hidden city routes actually have deals
    2. Then only geo-search those specific routes + the direct route

    Args:
        origin: Origin airport code (e.g., "GRU")
        destination: Destination airport code (e.g., "MCO")
        departure_date: Departure date (YYYY-MM-DD)
        locations: Country codes for geo search (default: all configured)
        max_concurrent: Max concurrent geo location searches
        headless: Run browsers headless
        initial_search_sources: Sources for initial search (default: all)
        initial_search_max_concurrent: Concurrency for initial hidden city search
        initial_search_quick: Use quick mode for initial search

    Returns:
        MultiRouteGeoResult with combined results
    """
    from src.parallel_search import search_flights, ParallelFlightSearch

    start_time = datetime.now()
    locations = locations or list(LOCATIONS.keys())

    logger.info(f"Starting hybrid geo search: {origin} → {destination}")
    logger.info(f"Phase 1: Running full parallel search to discover hidden city routes...")

    # ==========================================================================
    # PHASE 1: Run initial parallel search to discover hidden city routes
    # ==========================================================================
    phase1_start = datetime.now()

    if initial_search_quick:
        # Quick mode with limited routes
        search = ParallelFlightSearch(
            max_concurrent_hidden_city=initial_search_max_concurrent,
            headless=headless,
            num_hidden_city_routes=3,
        )
        initial_results = await search.search_all(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            sources=initial_search_sources,
        )
    else:
        initial_results = await search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            sources=initial_search_sources,
            max_concurrent=initial_search_max_concurrent,
            headless=headless,
        )

    phase1_time = (datetime.now() - phase1_start).total_seconds()
    logger.info(f"Phase 1 complete: {initial_results.total_flights_found} flights found in {phase1_time:.1f}s")

    # Get best direct price
    direct_best_price = None
    if initial_results.best_direct:
        direct_best_price = initial_results.best_direct.price_numeric

    # Extract hidden city routes
    hidden_city_routes = extract_hidden_city_routes(initial_results)
    logger.info(f"Found {len(hidden_city_routes)} hidden city routes worth geo-searching")

    # ==========================================================================
    # PHASE 2: Geo arbitrage on direct route + hidden city routes
    # ==========================================================================
    logger.info(f"Phase 2: Running geo arbitrage across {len(locations)} locations...")

    # Build list of routes to search
    routes_to_search: List[RouteInfo] = []

    # Always include the direct route
    routes_to_search.append(RouteInfo(
        origin=origin,
        destination=destination,
        route_type="direct",
        original_price=direct_best_price,
    ))

    # Add hidden city routes
    routes_to_search.extend(hidden_city_routes)

    # Ensure exchange rates are loaded
    converter = await ensure_rates_loaded()

    # Create geo search instance
    geo_search = GeoArbitrageSearch(
        locations=locations,
        max_concurrent=max_concurrent,
        headless=headless,
        sources=["google_flights"],  # Google Flights for geo (reliable pricing)
    )
    geo_search.converter = converter

    # Search all routes across all locations IN PARALLEL
    route_results: Dict[str, GeoArbitrageResult] = {}

    async def geo_search_route(route: RouteInfo) -> Tuple[str, Optional[GeoArbitrageResult]]:
        """Geo-search a single route across all locations."""
        route_key = f"{route.origin}-{route.destination}"
        route_label = f"{route.origin}→{route.destination}"
        if route.route_type == "hidden_city":
            route_label += f" (exit@{route.hidden_city_exit})"

        logger.info(f"Geo searching route: {route_label}")

        try:
            result = await geo_search.search(
                origin=route.origin,
                destination=route.destination,
                departure_date=departure_date,
            )

            if result.best_location and result.best_overall:
                logger.info(
                    f"  Best: ${result.best_overall.price_usd:.2f} from {result.best_location} "
                    f"(saves ${result.potential_savings_usd:.2f})"
                )
            return route_key, result
        except Exception as e:
            logger.error(f"Geo search failed for {route_key}: {e}")
            return route_key, None

    # Run all route geo-searches concurrently
    route_tasks = [geo_search_route(route) for route in routes_to_search]
    route_task_results = await asyncio.gather(*route_tasks, return_exceptions=True)

    for result in route_task_results:
        if isinstance(result, Exception):
            logger.error(f"Route geo-search task failed: {result}")
        elif result[1] is not None:
            route_results[result[0]] = result[1]

    # ==========================================================================
    # Save all geo results to database
    # ==========================================================================
    try:
        from src.database.flights_db import save_geo_search
        for route_key, result in route_results.items():
            save_geo_search(
                origin=route_key.split("-")[0],
                destination=route_key.split("-")[1],
                departure_date=departure_date,
                location_results=result.location_results,
            )
    except Exception as e:
        logger.warning(f"Failed to save to database: {e}")

    # ==========================================================================
    # PHASE 3: Analyze and compile results
    # ==========================================================================
    total_time = (datetime.now() - start_time).total_seconds()

    # Find best direct deal
    best_direct_deal = None
    direct_key = f"{origin}-{destination}"
    if direct_key in route_results:
        direct_result = route_results[direct_key]
        if direct_result.best_overall:
            best_direct_deal = {
                "route": direct_key,
                "best_location": direct_result.best_location,
                "best_price_usd": round(direct_result.best_overall.price_usd, 2),
                "original_currency": direct_result.best_overall.currency,
                "original_price": direct_result.best_overall.price_original,
                "airline": direct_result.best_overall.airline,
                "stops": direct_result.best_overall.stops,
                "layovers": direct_result.best_overall.layovers,
                "potential_savings_usd": round(direct_result.potential_savings_usd, 2),
                "potential_savings_pct": round(direct_result.potential_savings_pct, 1),
                "prices_by_location": {
                    loc: round(price, 2)
                    for loc, price in direct_result.price_comparison.items()
                },
            }

    # Find best hidden city deals
    best_hidden_city_deals = []
    for route in hidden_city_routes:
        route_key = f"{route.origin}-{route.destination}"
        if route_key in route_results:
            hc_result = route_results[route_key]
            if hc_result.best_overall:
                best_hidden_city_deals.append({
                    "route": route_key,
                    "exit_at": route.hidden_city_exit,
                    "best_location": hc_result.best_location,
                    "best_price_usd": round(hc_result.best_overall.price_usd, 2),
                    "original_price_usd": route.original_price,
                    "airline": hc_result.best_overall.airline,
                    "stops": hc_result.best_overall.stops,
                    "layovers": hc_result.best_overall.layovers,
                    "potential_savings_usd": round(hc_result.potential_savings_usd, 2),
                    "prices_by_location": {
                        loc: round(price, 2)
                        for loc, price in hc_result.price_comparison.items()
                    },
                })

    # Sort hidden city deals by price
    best_hidden_city_deals.sort(key=lambda x: x["best_price_usd"])

    # Calculate total potential savings
    total_savings = sum(
        result.potential_savings_usd
        for result in route_results.values()
        if result.potential_savings_usd > 0
    )

    return MultiRouteGeoResult(
        primary_origin=origin,
        primary_destination=destination,
        departure_date=departure_date,
        timestamp=datetime.now(),
        total_search_time_seconds=total_time,
        initial_search_time_seconds=phase1_time,
        direct_route_best_price=direct_best_price,
        hidden_city_routes_found=hidden_city_routes,
        route_results=route_results,
        best_direct_deal=best_direct_deal,
        best_hidden_city_deals=best_hidden_city_deals,
        total_routes_searched=len(routes_to_search),
        total_potential_savings_usd=total_savings,
    )
