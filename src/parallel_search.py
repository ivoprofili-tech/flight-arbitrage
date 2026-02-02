"""
Parallel Flight Search Engine

This module orchestrates concurrent flight searches across multiple sources:
1. Google Flights (direct route search)
2. Skiplagged (hidden city ticketing deals)
3. Hidden City Orchestrator (A→C searches looking for B layovers)

All searches run in parallel using asyncio for maximum efficiency.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
import logging

from src.models import (
    FlightResult,
    FlightSource,
    DealType,
    normalize_google_flight,
    normalize_skiplagged_flight,
    normalize_orchestrator_flight,
)

# Configure logging
logger = logging.getLogger(__name__)


class SearchStatus(Enum):
    """Status of an individual search operation."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class SearchSourceResult:
    """Result from a single search source."""
    source: FlightSource
    status: SearchStatus
    flights: List[FlightResult] = field(default_factory=list)
    error_message: Optional[str] = None
    search_time_seconds: float = 0.0


@dataclass
class ParallelSearchResult:
    """
    Consolidated result from all parallel searches.

    Contains results from each source, summary statistics,
    and the merged/deduplicated flight list.
    """
    # Search parameters
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None

    # Timing
    search_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_search_time_seconds: float = 0.0

    # Results by source
    source_results: Dict[str, SearchSourceResult] = field(default_factory=dict)

    # Consolidated results
    all_flights: List[FlightResult] = field(default_factory=list)

    # Summary statistics
    total_flights_found: int = 0
    sources_succeeded: List[str] = field(default_factory=list)
    sources_failed: List[str] = field(default_factory=list)

    # Best deals by category
    best_direct: Optional[FlightResult] = None
    best_skiplagged: Optional[FlightResult] = None
    best_hidden_city: Optional[FlightResult] = None
    best_overall: Optional[FlightResult] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "search_params": {
                "origin": self.origin,
                "destination": self.destination,
                "departure_date": self.departure_date,
                "return_date": self.return_date,
            },
            "timing": {
                "search_timestamp": self.search_timestamp,
                "total_search_time_seconds": round(self.total_search_time_seconds, 2),
            },
            "summary": {
                "total_flights_found": self.total_flights_found,
                "sources_succeeded": self.sources_succeeded,
                "sources_failed": self.sources_failed,
            },
            "best_deals": {
                "direct": self.best_direct.to_display_dict() if self.best_direct else None,
                "skiplagged": self.best_skiplagged.to_display_dict() if self.best_skiplagged else None,
                "hidden_city": self.best_hidden_city.to_display_dict() if self.best_hidden_city else None,
                "overall": self.best_overall.to_display_dict() if self.best_overall else None,
            },
            "source_details": {
                source: {
                    "status": result.status.value,
                    "flights_found": len(result.flights),
                    "search_time_seconds": round(result.search_time_seconds, 2),
                    "error": result.error_message,
                }
                for source, result in self.source_results.items()
            },
            "all_flights": [f.to_display_dict() for f in self.all_flights],
        }


class ParallelFlightSearch:
    """
    Parallel flight search engine that queries multiple sources concurrently.

    Usage:
        search = ParallelFlightSearch()
        results = await search.search_all(
            origin="GRU",
            destination="MCO",
            departure_date="2026-03-20"
        )
    """

    def __init__(
        self,
        google_flights_scraper=None,
        skiplagged_scraper=None,
        route_database=None,
        max_concurrent_hidden_city: int = 2,
        search_timeout_seconds: float = 120.0,
        per_source_timeout_seconds: float = 90.0,
    ):
        """
        Initialize the parallel search engine.

        Args:
            google_flights_scraper: Google Flights scraper instance
            skiplagged_scraper: Skiplagged scraper instance
            route_database: Route database for hidden city target selection
            max_concurrent_hidden_city: Max concurrent A→C searches in orchestrator
            search_timeout_seconds: Global timeout for entire search operation
            per_source_timeout_seconds: Timeout for each individual source
        """
        self.google_flights_scraper = google_flights_scraper
        self.skiplagged_scraper = skiplagged_scraper
        self.route_database = route_database
        self.max_concurrent_hidden_city = max_concurrent_hidden_city
        self.search_timeout_seconds = search_timeout_seconds
        self.per_source_timeout_seconds = per_source_timeout_seconds

    async def search_all(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> ParallelSearchResult:
        """
        Execute parallel searches across all enabled sources.

        Args:
            origin: Origin airport code (e.g., "GRU")
            destination: Destination airport code (e.g., "MCO")
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Optional return date for round-trip
            sources: Optional list of sources to search
                     ["google_flights", "skiplagged", "hidden_city"]
                     If None, searches all sources.

        Returns:
            ParallelSearchResult with consolidated flight data
        """
        start_time = asyncio.get_event_loop().time()

        # Default to all sources if not specified
        if sources is None:
            sources = ["google_flights", "skiplagged", "hidden_city"]

        # Normalize source names
        sources = [s.lower().replace("-", "_") for s in sources]

        logger.info(f"Starting parallel search: {origin} → {destination} on {departure_date}")
        logger.info(f"Sources: {sources}")

        # Build tasks for enabled sources
        tasks = []
        task_sources = []

        if "google_flights" in sources:
            tasks.append(self._search_google_direct(origin, destination, departure_date, return_date))
            task_sources.append(FlightSource.GOOGLE_FLIGHTS)

        if "skiplagged" in sources:
            tasks.append(self._search_skiplagged(origin, destination, departure_date, return_date))
            task_sources.append(FlightSource.SKIPLAGGED)

        if "hidden_city" in sources:
            tasks.append(self._search_hidden_city(origin, destination, departure_date))
            task_sources.append(FlightSource.HIDDEN_CITY)

        # Execute all searches in parallel with global timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.search_timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(f"Global search timeout after {self.search_timeout_seconds}s")
            results = [asyncio.TimeoutError() for _ in tasks]

        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time

        # Process results from each source
        source_results: Dict[str, SearchSourceResult] = {}
        all_flights: List[FlightResult] = []

        for source, result in zip(task_sources, results):
            source_name = source.value

            if isinstance(result, Exception):
                # Handle failed searches
                error_msg = str(result) if not isinstance(result, asyncio.TimeoutError) else "Timeout"
                status = SearchStatus.TIMEOUT if isinstance(result, asyncio.TimeoutError) else SearchStatus.FAILED

                source_results[source_name] = SearchSourceResult(
                    source=source,
                    status=status,
                    flights=[],
                    error_message=error_msg,
                )
                logger.warning(f"{source_name} search failed: {error_msg}")
            else:
                # Successful search
                flights, search_time = result
                source_results[source_name] = SearchSourceResult(
                    source=source,
                    status=SearchStatus.SUCCESS,
                    flights=flights,
                    search_time_seconds=search_time,
                )
                all_flights.extend(flights)
                logger.info(f"{source_name} found {len(flights)} flights in {search_time:.2f}s")

        # Deduplicate flights
        deduplicated = self._deduplicate_flights(all_flights)

        # Sort by price
        deduplicated.sort(key=lambda f: f.price_numeric)

        # Find best deals by category
        best_direct = self._find_best_by_source(deduplicated, FlightSource.GOOGLE_FLIGHTS)
        best_skiplagged = self._find_best_by_source(deduplicated, FlightSource.SKIPLAGGED)
        best_hidden_city = self._find_best_by_deal_type(deduplicated, DealType.HIDDEN_CITY)
        best_overall = deduplicated[0] if deduplicated else None

        # Build result
        result = ParallelSearchResult(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            total_search_time_seconds=total_time,
            source_results=source_results,
            all_flights=deduplicated,
            total_flights_found=len(deduplicated),
            sources_succeeded=[s for s, r in source_results.items() if r.status == SearchStatus.SUCCESS],
            sources_failed=[s for s, r in source_results.items() if r.status != SearchStatus.SUCCESS],
            best_direct=best_direct,
            best_skiplagged=best_skiplagged,
            best_hidden_city=best_hidden_city,
            best_overall=best_overall,
        )

        logger.info(f"Search complete: {len(deduplicated)} flights in {total_time:.2f}s")

        return result

    async def _search_google_direct(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
    ) -> Tuple[List[FlightResult], float]:
        """
        Search Google Flights for direct route A→B.

        Returns:
            Tuple of (normalized flights, search time in seconds)
        """
        start_time = asyncio.get_event_loop().time()

        try:
            if self.google_flights_scraper is None:
                raise RuntimeError("Google Flights scraper not configured")

            # Execute search with timeout
            raw_flights = await asyncio.wait_for(
                self._run_google_flights_search(origin, destination, departure_date, return_date),
                timeout=self.per_source_timeout_seconds
            )

            # Normalize results
            normalized = [
                normalize_google_flight(f, origin, destination)
                for f in raw_flights
            ]

            search_time = asyncio.get_event_loop().time() - start_time
            return normalized, search_time

        except asyncio.TimeoutError:
            logger.warning(f"Google Flights search timed out after {self.per_source_timeout_seconds}s")
            raise
        except Exception as e:
            logger.error(f"Google Flights search error: {e}")
            raise

    async def _run_google_flights_search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute the actual Google Flights scraper."""
        # Check if scraper has async search method
        if hasattr(self.google_flights_scraper, 'search_async'):
            return await self.google_flights_scraper.search_async(
                origin, destination, departure_date, return_date
            )
        elif hasattr(self.google_flights_scraper, 'search'):
            # Run sync method in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.google_flights_scraper.search(
                    origin, destination, departure_date, return_date
                )
            )
        else:
            raise RuntimeError("Google Flights scraper has no search method")

    async def _search_skiplagged(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
    ) -> Tuple[List[FlightResult], float]:
        """
        Search Skiplagged for flight deals.

        Returns:
            Tuple of (normalized flights, search time in seconds)
        """
        start_time = asyncio.get_event_loop().time()

        try:
            if self.skiplagged_scraper is None:
                raise RuntimeError("Skiplagged scraper not configured")

            # Execute search with timeout
            raw_flights = await asyncio.wait_for(
                self._run_skiplagged_search(origin, destination, departure_date, return_date),
                timeout=self.per_source_timeout_seconds
            )

            # Normalize results
            normalized = [
                normalize_skiplagged_flight(f, origin, destination)
                for f in raw_flights
            ]

            search_time = asyncio.get_event_loop().time() - start_time
            return normalized, search_time

        except asyncio.TimeoutError:
            logger.warning(f"Skiplagged search timed out after {self.per_source_timeout_seconds}s")
            raise
        except Exception as e:
            logger.error(f"Skiplagged search error: {e}")
            raise

    async def _run_skiplagged_search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Execute the actual Skiplagged scraper."""
        # Check if scraper has async search method
        if hasattr(self.skiplagged_scraper, 'search_async'):
            return await self.skiplagged_scraper.search_async(
                origin, destination, departure_date, return_date
            )
        elif hasattr(self.skiplagged_scraper, 'search'):
            # Run sync method in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.skiplagged_scraper.search(
                    origin, destination, departure_date, return_date
                )
            )
        else:
            raise RuntimeError("Skiplagged scraper has no search method")

    async def _search_hidden_city(
        self,
        origin: str,
        destination: str,
        departure_date: str,
    ) -> Tuple[List[FlightResult], float]:
        """
        Search for hidden city deals by running multiple A→C searches.

        This method:
        1. Gets target C destinations from route database
        2. Runs parallel A→C searches (with concurrency limit)
        3. Filters for flights that have destination (B) as a layover

        Returns:
            Tuple of (normalized flights with hidden city metadata, search time)
        """
        start_time = asyncio.get_event_loop().time()

        try:
            if self.google_flights_scraper is None:
                raise RuntimeError("Google Flights scraper not configured")

            # Get target C destinations from route database
            target_routes = self._get_hidden_city_targets(origin, destination)

            if not target_routes:
                logger.warning(f"No hidden city routes configured for {origin} → {destination}")
                return [], asyncio.get_event_loop().time() - start_time

            logger.info(f"Searching {len(target_routes)} hidden city routes: {target_routes}")

            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(self.max_concurrent_hidden_city)

            async def search_single_route(final_dest: str) -> List[Dict[str, Any]]:
                """Search a single A→C route with semaphore control."""
                async with semaphore:
                    try:
                        raw_flights = await asyncio.wait_for(
                            self._run_google_flights_search(origin, final_dest, departure_date),
                            timeout=self.per_source_timeout_seconds
                        )

                        # Filter and annotate flights with hidden city metadata
                        return self._process_hidden_city_flights(
                            raw_flights,
                            origin=origin,
                            hidden_city_target=destination,
                            final_destination=final_dest,
                        )
                    except Exception as e:
                        logger.warning(f"Hidden city search {origin}→{final_dest} failed: {e}")
                        return []

            # Run all A→C searches in parallel
            route_results = await asyncio.gather(
                *[search_single_route(dest) for dest in target_routes],
                return_exceptions=True
            )

            # Flatten and collect results
            all_hidden_city_flights: List[FlightResult] = []
            for result in route_results:
                if isinstance(result, list):
                    all_hidden_city_flights.extend(result)

            search_time = asyncio.get_event_loop().time() - start_time
            return all_hidden_city_flights, search_time

        except Exception as e:
            logger.error(f"Hidden city search error: {e}")
            raise

    def _get_hidden_city_targets(self, origin: str, destination: str) -> List[str]:
        """
        Get list of C destinations to search for hidden city deals.

        Uses route database if available, otherwise returns empty list.
        """
        if self.route_database is None:
            return []

        # Try to get pair-specific routes first
        if hasattr(self.route_database, 'get_target_routes'):
            return self.route_database.get_target_routes(destination, origin=origin)
        elif hasattr(self.route_database, 'get_routes'):
            return self.route_database.get_routes(origin, destination)
        elif isinstance(self.route_database, dict):
            # Simple dict-based route database
            pair_key = (origin, destination)
            if pair_key in self.route_database:
                return self.route_database[pair_key]
            elif destination in self.route_database:
                return self.route_database[destination]

        return []

    def _process_hidden_city_flights(
        self,
        raw_flights: List[Dict[str, Any]],
        origin: str,
        hidden_city_target: str,
        final_destination: str,
    ) -> List[FlightResult]:
        """
        Process raw flights from A→C search and identify hidden city opportunities.

        Checks if hidden_city_target (B) appears as a layover in each flight.
        """
        results: List[FlightResult] = []
        target_variants = self._get_city_variants(hidden_city_target)

        for flight in raw_flights:
            layovers = flight.get('layovers', [])
            if isinstance(layovers, str):
                layovers = [layovers] if layovers else []

            # Check if target city is a layover
            confirmed_layover = False
            for layover in layovers:
                layover_upper = layover.upper().strip()
                if layover_upper in target_variants:
                    confirmed_layover = True
                    break

            # Determine deal type
            if confirmed_layover:
                deal_type = "hidden_city"
            elif layovers:
                deal_type = "not_target_layover"
            else:
                # No layover info - could still be a hidden city
                deal_type = "potential_hidden_city"

            # Only include confirmed or potential hidden city deals
            if deal_type in ("hidden_city", "potential_hidden_city"):
                # Enrich flight data with hidden city metadata
                enriched = {
                    **flight,
                    'final_destination': final_destination,
                    'hidden_city_target': hidden_city_target,
                    'search_route': f"{origin} → {final_destination}",
                    'deal_type': deal_type,
                    'confirmed_layover': confirmed_layover,
                }

                normalized = normalize_orchestrator_flight(
                    enriched,
                    origin=origin,
                    hidden_city_target=hidden_city_target,
                )
                results.append(normalized)

        return results

    def _get_city_variants(self, airport_code: str) -> Set[str]:
        """
        Generate variants of an airport code for matching.

        Examples:
            "MCO" → {"MCO", "ORLANDO", "ORL"}
            "JFK" → {"JFK", "NEW YORK", "NYC", "NEWYORK"}
        """
        code = airport_code.upper().strip()
        variants = {code}

        # Common airport code to city name mappings
        city_mappings = {
            "MCO": ["ORLANDO", "ORL"],
            "JFK": ["NEW YORK", "NYC", "NEWYORK"],
            "EWR": ["NEWARK", "NEW YORK", "NYC"],
            "LGA": ["LAGUARDIA", "NEW YORK", "NYC"],
            "LAX": ["LOS ANGELES", "LA"],
            "SFO": ["SAN FRANCISCO", "SF"],
            "ORD": ["CHICAGO", "CHI", "O'HARE"],
            "DFW": ["DALLAS", "DAL", "FORT WORTH"],
            "DEN": ["DENVER"],
            "ATL": ["ATLANTA"],
            "MIA": ["MIAMI"],
            "FLL": ["FORT LAUDERDALE", "FT LAUDERDALE"],
            "TPA": ["TAMPA"],
            "PHX": ["PHOENIX"],
            "SEA": ["SEATTLE"],
            "BOS": ["BOSTON"],
            "DCA": ["WASHINGTON", "DC", "REAGAN"],
            "IAD": ["DULLES", "WASHINGTON", "DC"],
            "GRU": ["SAO PAULO", "GUARULHOS"],
            "GIG": ["RIO DE JANEIRO", "RIO", "GALEAO"],
        }

        if code in city_mappings:
            variants.update(city_mappings[code])

        return variants

    def _deduplicate_flights(self, flights: List[FlightResult]) -> List[FlightResult]:
        """
        Remove duplicate flights based on deduplication key.

        When duplicates are found, prefer the result with more metadata
        (e.g., prefer hidden_city source if it has confirmed layover info).
        """
        seen: Dict[str, FlightResult] = {}

        for flight in flights:
            key = flight.dedup_key

            if key not in seen:
                seen[key] = flight
            else:
                # Choose the better result
                existing = seen[key]

                # Prefer confirmed hidden city deals
                if (flight.deal_type == DealType.HIDDEN_CITY and
                    existing.deal_type != DealType.HIDDEN_CITY):
                    seen[key] = flight
                # Prefer results with layover info
                elif flight.layovers and not existing.layovers:
                    seen[key] = flight
                # Prefer skiplagged deals with savings info
                elif (flight.source == FlightSource.SKIPLAGGED and
                      flight.savings and not existing.savings):
                    seen[key] = flight

        return list(seen.values())

    def _find_best_by_source(
        self,
        flights: List[FlightResult],
        source: FlightSource
    ) -> Optional[FlightResult]:
        """Find the cheapest flight from a specific source."""
        source_flights = [f for f in flights if f.source == source]
        if not source_flights:
            return None
        return min(source_flights, key=lambda f: f.price_numeric)

    def _find_best_by_deal_type(
        self,
        flights: List[FlightResult],
        deal_type: DealType
    ) -> Optional[FlightResult]:
        """Find the cheapest flight of a specific deal type."""
        matching = [f for f in flights if f.deal_type == deal_type]
        if not matching:
            return None
        return min(matching, key=lambda f: f.price_numeric)


async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    google_flights_scraper=None,
    skiplagged_scraper=None,
    route_database=None,
    sources: Optional[List[str]] = None,
    max_concurrent: int = 2,
) -> ParallelSearchResult:
    """
    Convenience function to run a parallel flight search.

    This is the main entry point for running searches.

    Args:
        origin: Origin airport code
        destination: Destination airport code
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Optional return date
        google_flights_scraper: Google Flights scraper instance
        skiplagged_scraper: Skiplagged scraper instance
        route_database: Route database for hidden city targets
        sources: List of sources to search (default: all)
        max_concurrent: Max concurrent hidden city searches

    Returns:
        ParallelSearchResult with all flight data

    Example:
        results = await search_flights(
            origin="GRU",
            destination="MCO",
            departure_date="2026-03-20",
            google_flights_scraper=gf_scraper,
            skiplagged_scraper=sl_scraper,
            route_database=routes,
        )

        print(f"Found {results.total_flights_found} flights")
        print(f"Best price: {results.best_overall.price}")
    """
    search = ParallelFlightSearch(
        google_flights_scraper=google_flights_scraper,
        skiplagged_scraper=skiplagged_scraper,
        route_database=route_database,
        max_concurrent_hidden_city=max_concurrent,
    )

    return await search.search_all(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        sources=sources,
    )
