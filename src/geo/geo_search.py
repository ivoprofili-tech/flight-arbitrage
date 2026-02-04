"""
Geo Arbitrage Search Orchestrator

Runs parallel flight searches from multiple geographic locations
and compares prices to find the best Point of Sale (POS).

Usage:
    results = await search_with_geo_arbitrage(
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
from typing import Dict, List, Optional, Any
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
from src.scraper.google_flights import search_google_flights
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "airline": self.airline,
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

        # Get proxy for this location
        proxy_config = get_proxy_for_location(location)
        proxy_dict = proxy_config.to_playwright_proxy() if proxy_config else None

        if not proxy_dict:
            logger.warning(f"No proxy configured for {location}, searching without geo-targeting")

        flights: List[GeoFlightResult] = []

        try:
            # Search Google Flights if enabled
            if "google_flights" in self.sources:
                gf_flights = await search_google_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    headless=self.headless,
                    proxy=proxy_dict,
                    locale=location_config.locale,
                    language=location_config.language,
                    geo_location=location,
                )

                # Convert to GeoFlightResult
                for f in gf_flights:
                    if "error" in f:
                        continue

                    price_str = f.get("price", "$0")
                    amount, currency = parse_price(price_str)

                    # Use expected currency from location if price looks like USD but location uses different
                    if currency == "USD" and location_config.currency != "USD":
                        # Check if price might actually be in local currency
                        # (Google sometimes shows $ for other currencies)
                        pass  # Keep detected currency for now

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
                        source=SearchSource.GOOGLE_FLIGHTS,
                        layovers=f.get("layovers", []),
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
