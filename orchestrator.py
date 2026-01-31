"""
Skiplagging Orchestrator (Root Module)
======================================
This is a convenience wrapper that re-exports from src/orchestrator.py
for easier imports when running scripts from the project root.

Usage:
    from orchestrator import search_skiplag_deals
    # or
    python -m orchestrator JFK DEN 2025-03-15
"""

# Re-export everything from the src module
from src.orchestrator import (
    execute_targeted_skiplag_search,
    search_skiplag_deals,
    _get_city_variants,
    _check_layovers_list,
    _check_for_layover,
    _parse_price,
)

__all__ = [
    'execute_targeted_skiplag_search',
    'search_skiplag_deals',
]

# Allow running as a script
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        """Command-line interface for the orchestrator."""
        print("=" * 60)
        print("SKIPLAGGING DEAL FINDER")
        print("=" * 60)

        if len(sys.argv) < 4:
            print("\nUsage: python orchestrator.py <origin> <destination> <date> [target1,target2,...]")
            print("\nExample:")
            print("  python orchestrator.py JFK DEN 2025-03-15 LAX,SFO,SEA")
            print("\nThis searches JFK→LAX, JFK→SFO, JFK→SEA looking for DEN layovers")
            print("(You want to go to DEN, so search flights to cities BEYOND DEN)")
            return

        origin = sys.argv[1]
        destination = sys.argv[2]
        date = sys.argv[3]

        if len(sys.argv) > 4:
            target_routes = sys.argv[4].split(',')
        else:
            target_routes = None

        deals = await search_skiplag_deals(
            origin=origin,
            destination=destination,
            date=date,
            target_routes=target_routes,
            headless=True
        )

        if deals:
            print("\n" + "=" * 60)
            print("POTENTIAL DEALS")
            print("=" * 60)

            for i, deal in enumerate(deals, 1):
                deal_type = "✓ CONFIRMED" if deal.get('deal_type') == 'hidden_city' else "? POTENTIAL"
                print(f"\n[{i}] {deal_type}")
                print(f"    Route: {deal.get('search_route', 'N/A')}")
                print(f"    Price: {deal.get('price', 'N/A')}")
                print(f"    Layovers: {deal.get('layovers', [])}")
                if deal.get('note'):
                    print(f"    Note: {deal.get('note')}")
        else:
            print("\nNo deals found. Try different target routes or dates.")

    asyncio.run(main())
