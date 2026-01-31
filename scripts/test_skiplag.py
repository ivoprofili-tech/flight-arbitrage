#!/usr/bin/env python3
"""
Test script for the skiplagging orchestrator.

This script tests the hidden-city fare search functionality by:
1. Searching for flights from a major hub to various destinations
2. Looking for flights where our true destination appears as a layover
3. Displaying any hidden-city opportunities found

Usage:
    python scripts/test_skiplag.py

Hidden-City Concept:
    You want to fly JFK -> PHX (Phoenix)
    We search JFK -> LAX, JFK -> SAN, JFK -> SFO (cities BEYOND Phoenix)
    If a JFK -> LAX flight stops in PHX, that's a hidden-city opportunity!
    You book JFK -> LAX but get off at the PHX layover.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import execute_targeted_skiplag_search, search_skiplag_deals


async def test_targeted_search():
    """
    Test the targeted skiplag search with specific routes.
    
    Scenario: Flying from JFK to Denver (DEN)
    We search for flights to West Coast cities (LAX, SFO) that might
    stop in Denver as a layover.
    """
    print("=" * 60)
    print("SKIPLAGGING ORCHESTRATOR TEST")
    print("=" * 60)
    print()
    
    # Set up test parameters
    origin = "JFK"
    true_destination = "DEN"  # Where we actually want to go (Denver)
    
    # Calculate departure date (2 weeks from now)
    departure = datetime.now() + timedelta(days=14)
    departure_str = departure.strftime('%Y-%m-%d')
    
    # Routes BEYOND Denver that might have DEN as a layover
    # Flights from East Coast to West Coast often stop in Denver
    target_routes = ["LAX", "SFO"]  # Start with just 2 for faster testing
    
    print(f"Test Configuration:")
    print(f"  Origin: {origin}")
    print(f"  True Destination: {true_destination} (looking for this as a LAYOVER)")
    print(f"  Departure Date: {departure_str}")
    print(f"  Searching routes: {origin} → {', '.join(target_routes)}")
    print(f"  Strategy: Find {origin}→{target_routes[0]} flights that STOP at {true_destination}")
    print()
    print("-" * 60)
    print()
    
    try:
        # Run the targeted search
        results = await execute_targeted_skiplag_search(
            origin_A=origin,
            destination_B=true_destination,
            date=departure_str,
            target_routes=target_routes,
            headless=True,  # Set to False to watch the browser
            max_concurrent=2  # Limit concurrent searches
        )
        
        print()
        print("=" * 60)
        print("DETAILED RESULTS")
        print("=" * 60)
        
        if results:
            # Separate confirmed deals from potential ones
            confirmed = [r for r in results if r.get('deal_type') == 'hidden_city']
            potential = [r for r in results if r.get('deal_type') != 'hidden_city']
            
            print(f"\n✓ Found {len(results)} total opportunities")
            print(f"  - Confirmed hidden-city deals (layover at {true_destination}): {len(confirmed)}")
            print(f"  - Other connecting flights: {len(potential)}")
            
            if confirmed:
                print("\n" + "-" * 40)
                print(f"CONFIRMED HIDDEN-CITY DEALS (layover at {true_destination})")
                print("-" * 40)
                for i, flight in enumerate(confirmed, 1):
                    print(f"\n[{i}] {flight.get('price', 'N/A')}")
                    print(f"    Route searched: {flight.get('search_route', 'N/A')}")
                    print(f"    Get off at: {flight.get('hidden_city_target', 'N/A')}")
                    print(f"    Layovers: {flight.get('layovers', [])}")
                    print(f"    Airline: {flight.get('airline', 'N/A')}")
                    print(f"    Times: {flight.get('departure_time', 'N/A')} → {flight.get('arrival_time', 'N/A')}")
                    print(f"    Duration: {flight.get('duration', 'N/A')}")
                    print(f"    Stops: {flight.get('stops', 'N/A')}")
            
            if potential:
                print("\n" + "-" * 40)
                print("OTHER CONNECTING FLIGHTS (different layovers)")
                print("-" * 40)
                for i, flight in enumerate(potential[:5], 1):  # Show top 5
                    print(f"\n[{i}] {flight.get('price', 'N/A')}")
                    print(f"    Route: {flight.get('search_route', 'N/A')}")
                    print(f"    Stops: {flight.get('stops', 'N/A')}")
                    print(f"    Layovers: {flight.get('layovers', [])}")
                    if flight.get('note'):
                        print(f"    Note: {flight.get('note')}")
        else:
            print(f"\nNo hidden-city opportunities found for this search.")
            print("This could mean:")
            print(f"  - No flights on these routes have {true_destination} as a layover")
            print("  - The scraper couldn't extract layover information")
            print("  - Try different target routes or dates")
        
        return results
        
    except Exception as e:
        print(f"\n✗ Error during search: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_auto_search():
    """
    Test the automatic skiplag deals search.
    
    This uses the search_skiplag_deals function which automatically
    determines good target routes based on the destination.
    """
    print()
    print("=" * 60)
    print("AUTO SKIPLAG SEARCH TEST")
    print("=" * 60)
    print()
    
    origin = "JFK"
    destination = "DEN"  # Denver - common layover hub, has default targets
    
    departure = datetime.now() + timedelta(days=21)
    departure_str = departure.strftime('%Y-%m-%d')
    
    print(f"Test Configuration:")
    print(f"  Origin: {origin}")
    print(f"  Destination: {destination} (looking for this as a LAYOVER)")
    print(f"  Departure: {departure_str}")
    print(f"  (Auto-selecting target routes - cities beyond {destination})")
    print()
    
    try:
        results = await search_skiplag_deals(
            origin=origin,
            destination=destination,
            date=departure_str,
            headless=True
        )
        
        if results:
            confirmed = [r for r in results if r.get('deal_type') == 'hidden_city']
            print(f"\n✓ Found {len(results)} total deals ({len(confirmed)} confirmed at {destination})")
            for i, deal in enumerate(results[:5], 1):  # Show top 5
                status = "✓" if deal.get('deal_type') == 'hidden_city' else "?"
                print(f"  [{status}] {deal.get('price', 'N/A')} - {deal.get('search_route')} (layovers: {deal.get('layovers', [])})")
        else:
            print("\nNo deals found with auto-search.")
            
        return results
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("STARTING SKIPLAG ORCHESTRATOR TESTS")
    print("=" * 60 + "\n")
    
    # Test 1: Targeted search (smaller, faster test)
    targeted_results = await test_targeted_search()
    
    # Test 2: Auto search (uncomment to run - takes longer)
    # auto_results = await test_auto_search()
    
    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)
    
    return targeted_results


if __name__ == "__main__":
    asyncio.run(main())
