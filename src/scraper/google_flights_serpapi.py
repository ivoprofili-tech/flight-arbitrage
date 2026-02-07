"""
Google Flights Scraper via SerpApi
===================================
Replaces Playwright browser automation with SerpApi's Google Flights API.

Instead of launching a browser, filling forms, and parsing HTML, this module
makes a single HTTP request and gets structured JSON back.

SerpApi handles:
- Browser rendering and JavaScript execution
- CAPTCHA solving and bot detection
- Geo-targeting via the `gl` parameter (replaces BrightData proxies)
- HTML parsing into structured data

Key advantages:
- ~2 seconds per search (vs ~30+ seconds with Playwright)
- No breakage when Google changes their HTML
- Structured JSON with airport codes, layovers, durations, etc.
- No browser/Playwright dependency for Google Flights

Usage:
    flights = await search_google_flights(
        origin="GRU",
        destination="MCO",
        departure_date="2026-03-15",
        geo_location="BR",        # uses SerpApi's gl parameter
    )

Environment:
    SERPAPI_KEY: Your SerpApi API key (required)
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# SerpApi endpoint
SERPAPI_URL = "https://serpapi.com/search.json"


async def _call_serpapi(params: dict) -> dict:
    """
    Make an async HTTP request to SerpApi.

    Args:
        params: Query parameters including engine, api_key, etc.

    Returns:
        Parsed JSON response as dict.

    Raises:
        ValueError: If API returns an error or API key is missing.
        aiohttp.ClientError: On network errors.
    """
    api_key = params.get("api_key") or os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        raise ValueError(
            "SerpApi API key not set. Set SERPAPI_KEY environment variable "
            "or pass api_key parameter."
        )

    params["api_key"] = api_key

    async with aiohttp.ClientSession() as session:
        async with session.get(SERPAPI_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    # Check for API-level errors
    if "error" in data:
        raise ValueError(f"SerpApi error: {data['error']}")

    status = data.get("search_metadata", {}).get("status")
    if status and status != "Success":
        raise ValueError(f"SerpApi search failed with status: {status}")

    return data


def _format_duration(minutes: int) -> str:
    """Convert duration in minutes to 'Xh Ym' string."""
    if not minutes:
        return ""
    h = minutes // 60
    m = minutes % 60
    if h and m:
        return f"{h}h {m}m"
    elif h:
        return f"{h}h 0m"
    else:
        return f"{m}m"


def _format_time(time_str: str) -> str:
    """
    Convert SerpApi time format '2026-03-15 08:25' to '8:25 AM'.

    Falls back to returning the original string if parsing fails.
    """
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        return dt.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return time_str or ""


def _format_stops(layovers: list) -> str:
    """Convert layovers list to stops string like 'Nonstop', '1 stop', '2 stops'."""
    n = len(layovers)
    if n == 0:
        return "Nonstop"
    elif n == 1:
        return "1 stop"
    else:
        return f"{n} stops"


def _parse_flight(flight_data: dict, currency: str) -> dict:
    """
    Convert a single SerpApi flight result into the dict format expected
    by normalize_google_flight() and the rest of the codebase.

    SerpApi returns:
        {
            "flights": [{ "departure_airport": {...}, "arrival_airport": {...}, ... }],
            "layovers": [{ "id": "ATL", "duration": 95, ... }],
            "total_duration": 455,
            "price": 179,
            ...
        }

    We convert to:
        {
            "airline": "Delta",
            "departure_time": "8:25 AM",
            "arrival_time": "6:40 PM",
            "duration": "7h 35m",
            "stops": "1 stop",
            "price": "$179",
            "layovers": ["ATL"],
        }
    """
    segments = flight_data.get("flights", [])
    layovers = flight_data.get("layovers", [])

    if not segments:
        return None

    # First and last segment give departure/arrival
    first_seg = segments[0]
    last_seg = segments[-1]

    dep_time = first_seg.get("departure_airport", {}).get("time", "")
    arr_time = last_seg.get("arrival_airport", {}).get("time", "")

    # Airline: use first segment's airline, or join multiple if different
    airlines = []
    for seg in segments:
        name = seg.get("airline", "")
        if name and name not in airlines:
            airlines.append(name)
    airline = ", ".join(airlines) if airlines else "Unknown"

    # Duration
    total_duration = flight_data.get("total_duration", 0)
    duration_str = _format_duration(total_duration)

    # Stops
    stops_str = _format_stops(layovers)

    # Layover airport codes
    layover_codes = [lay.get("id", "") for lay in layovers if lay.get("id")]

    # Price — include actual currency code so downstream parse_price()
    # correctly identifies BRL, COP, etc. instead of assuming USD
    price_val = flight_data.get("price", 0)
    if currency and currency.upper() != "USD":
        price_str = f"{currency.upper()} {price_val}" if price_val else f"{currency.upper()} 0"
    else:
        price_str = f"${price_val}" if price_val else "$0"

    return {
        "airline": airline,
        "departure_time": _format_time(dep_time),
        "arrival_time": _format_time(arr_time),
        "duration": duration_str,
        "stops": stops_str,
        "price": price_str,
        "layovers": layover_codes,
    }


async def search_google_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    headless: bool = True,       # Ignored -- kept for API compatibility
    fast_mode: bool = True,      # Ignored -- kept for API compatibility
    proxy: dict = None,          # Ignored -- SerpApi handles this via gl param
    locale: str = None,          # Ignored -- use geo_location instead
    language: str = None,        # Ignored -- we use hl=en
    geo_location: str = None,
    api_key: str = None,
    currency: str = "USD",
    stops: int = 0,
    show_hidden: bool = True,
) -> list[dict]:
    """
    Search Google Flights via SerpApi.

    Drop-in replacement for the Playwright-based search_google_flights().
    Returns the same dict format so normalize_google_flight() works unchanged.

    Args:
        origin: Origin airport code (e.g., "GRU")
        destination: Destination airport code (e.g., "MCO")
        departure_date: Date in YYYY-MM-DD format
        return_date: Optional return date for round-trip
        headless: Ignored (no browser needed)
        fast_mode: Ignored (API is always fast)
        proxy: Ignored (SerpApi handles geo via gl parameter)
        locale: Ignored (use geo_location for POS targeting)
        language: Ignored (we always request English results)
        geo_location: Country code for Point of Sale (e.g., "BR", "US", "CO")
                     Maps to SerpApi's gl parameter.
        api_key: SerpApi key (or set SERPAPI_KEY env var)
        currency: Currency code (default "USD")
        stops: 0=any, 1=nonstop, 2=1 stop or fewer, 3=2 stops or fewer
        show_hidden: Show additional flight results (default True)

    Returns:
        List of flight dicts compatible with normalize_google_flight()
    """
    # Build SerpApi parameters
    params = {
        "engine": "google_flights",
        "departure_id": origin.upper(),
        "arrival_id": destination.upper(),
        "outbound_date": departure_date,
        "hl": "en",
        "currency": currency,
    }

    if api_key:
        params["api_key"] = api_key

    # Trip type
    if return_date:
        params["type"] = "1"  # Round trip
        params["return_date"] = return_date
    else:
        params["type"] = "2"  # One way

    # Geo-location (Point of Sale) -- this replaces BrightData proxies
    if geo_location:
        params["gl"] = geo_location.lower()

    # Filters
    if stops:
        params["stops"] = str(stops)

    if show_hidden:
        params["show_hidden"] = "true"

    # Make the API call
    logger.info(f"SerpApi search: {origin} → {destination} on {departure_date} (gl={geo_location or 'default'})")

    try:
        data = await _call_serpapi(params)
    except Exception as e:
        logger.error(f"SerpApi request failed: {e}")
        return [{
            "error": str(e),
            "layovers": [],
            "note": f"SerpApi request failed: {e}",
        }]

    # Parse flights from response
    best_flights = data.get("best_flights", [])
    other_flights = data.get("other_flights", [])
    all_raw = best_flights + other_flights

    if not all_raw:
        logger.warning(f"No flights found for {origin} → {destination} on {departure_date}")
        return []

    # Convert each flight to the expected dict format
    flights = []
    for raw in all_raw:
        # Skip flights with no price (SerpApi returns price=0 or missing for unpriced flights)
        raw_price = raw.get("price", 0)
        if not raw_price or (isinstance(raw_price, (int, float)) and raw_price <= 0):
            continue
        parsed = _parse_flight(raw, currency)
        if parsed:
            flights.append(parsed)

    logger.info(f"SerpApi returned {len(flights)} flights for {origin} → {destination}")
    return flights


# Keep save_results_to_file for backward compatibility
def save_results_to_file(
    flights: list[dict],
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    filename: str = None,
) -> str:
    """Save flight search results to a text file."""
    if filename is None:
        origin_clean = origin.replace(" ", "_").replace(",", "")
        dest_clean = destination.replace(" ", "_").replace(",", "")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flights_{origin_clean}_to_{dest_clean}_{timestamp}.txt"

    lines = []
    lines.append("=" * 60)
    lines.append("FLIGHT SEARCH RESULTS (via SerpApi)")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Search performed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Route: {origin} → {destination}")
    lines.append(f"Departure: {departure_date}")
    if return_date:
        lines.append(f"Return: {return_date}")
    else:
        lines.append("Trip type: One-way")
    lines.append("")
    lines.append("-" * 60)
    lines.append(f"Found {len(flights)} flight(s)")
    lines.append("-" * 60)
    lines.append("")

    if flights:
        for i, flight in enumerate(flights, 1):
            lines.append(f"FLIGHT {i}")
            lines.append("-" * 30)
            for key, value in flight.items():
                nice_key = key.replace("_", " ").title()
                lines.append(f"  {nice_key}: {value}")
            lines.append("")
    else:
        lines.append("No flights found.")
        lines.append("")

    lines.append("=" * 60)
    lines.append("End of results")
    lines.append("=" * 60)

    content = "\n".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\nResults saved to: {filename}")
    return filename
