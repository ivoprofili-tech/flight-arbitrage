"""
Skyscanner Flight Scraper
=========================
This script uses Playwright to automate a web browser and scrape flight data
from Skyscanner.

Similar to the Google Flights scraper, but adapted for Skyscanner's interface.
"""

import asyncio
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class SkyscannerScraper:
    """
    A class to scrape flight data from Skyscanner.
    """

    def __init__(self, headless: bool = True):
        """
        Initialize the scraper.

        Args:
            headless: If True, browser runs invisibly in background.
        """
        self.headless = headless
        self.browser = None
        self.page = None
        self.context = None

    async def start_browser(self):
        """Launch the browser with video recording enabled."""
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )

        # Ensure videos directory exists
        os.makedirs('videos', exist_ok=True)

        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            record_video_dir='videos/',
            record_video_size={'width': 1280, 'height': 800}
        )

        self.page = await self.context.new_page()
        print("Browser started! Video recording enabled (saves to videos/ folder)")

    async def close_browser(self):
        """Clean up: close the browser and save the video."""
        video_path = None

        if self.page:
            try:
                video = self.page.video
                if video:
                    video_path = await video.path()
            except:
                pass

        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        if video_path:
            print(f"\n{'='*50}")
            print(f"VIDEO SAVED: {video_path}")
            print(f"{'='*50}")
            print("Download this file to watch the scraping session")
        else:
            print("Browser closed (no video saved).")

    async def handle_cookie_consent(self):
        """Handle cookie consent popup on Skyscanner."""
        try:
            cookie_selectors = [
                'button#onetrust-accept-btn-handler',
                'button:has-text("Accept all")',
                'button:has-text("Accept")',
                'button:has-text("I accept")',
                '[data-testid="accept-button"]',
            ]

            for selector in cookie_selectors:
                try:
                    button = await self.page.wait_for_selector(selector, timeout=500)
                    if button:
                        await button.click()
                        print("  ✓ Accepted cookies")
                        await self.page.wait_for_timeout(300)
                        return True
                except PlaywrightTimeout:
                    continue

            return False

        except Exception:
            return False

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = None
    ) -> list[dict]:
        """
        Search for flights on Skyscanner.

        Args:
            origin: Departure city or airport code
            destination: Arrival city or airport code
            departure_date: Date in YYYY-MM-DD format
            return_date: Optional return date in YYYY-MM-DD format

        Returns:
            List of flight dictionaries
        """
        print(f"\nSearching Skyscanner: {origin} → {destination}")
        print(f"Departure: {departure_date}" + (f", Return: {return_date}" if return_date else " (one-way)"))

        # Build the Skyscanner URL directly (more reliable than form filling)
        # Skyscanner URL format: /transport/flights/{origin}/{destination}/{date}/{return_date}/
        origin_code = origin.replace(" ", "-").lower()
        dest_code = destination.replace(" ", "-").lower()

        # Format date as YYMMDD for URL
        dep_date = datetime.strptime(departure_date, '%Y-%m-%d')
        date_str = dep_date.strftime('%y%m%d')

        if return_date:
            ret_date = datetime.strptime(return_date, '%Y-%m-%d')
            ret_str = ret_date.strftime('%y%m%d')
            url = f"https://www.skyscanner.com/transport/flights/{origin_code}/{dest_code}/{date_str}/{ret_str}/"
        else:
            url = f"https://www.skyscanner.com/transport/flights/{origin_code}/{dest_code}/{date_str}/"

        # Step 1: Open Skyscanner search page
        print("\n[Step 1] Opening Skyscanner...")
        await self.page.goto(url, wait_until='domcontentloaded')
        await self.page.wait_for_timeout(2000)

        # Handle cookie consent
        await self.handle_cookie_consent()

        # Step 2: Wait for results to load
        print("[Step 2] Waiting for flight results...")
        await self._wait_for_results()

        # Step 3: Extract flight data
        print("[Step 3] Extracting flight data...")
        await self.page.screenshot(path='debug_skyscanner.png')
        flights = await self._extract_flights()

        print(f"\nFound {len(flights)} flights on Skyscanner!")
        return flights

    async def _wait_for_results(self):
        """Wait for Skyscanner results to load."""
        try:
            # Wait for flight results container
            result_selectors = [
                '[data-testid="flight-card"]',
                '[class*="FlightCard"]',
                '[class*="ResultCard"]',
                '[class*="itinerary"]',
                'div[class*="BpkTicket"]',
            ]

            for selector in result_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=10000)
                    print("  ✓ Results loaded")
                    await self.page.wait_for_timeout(2000)
                    return
                except PlaywrightTimeout:
                    continue

            # Fallback: just wait
            print("  ⚠ Could not detect results container, waiting...")
            await self.page.wait_for_timeout(5000)

        except Exception as e:
            print(f"  ⚠ Error waiting for results: {e}")
            await self.page.wait_for_timeout(5000)

    async def _extract_flights(self) -> list[dict]:
        """Extract flight information from Skyscanner results."""
        flights = []

        try:
            # Save page text for debugging
            page_text = await self.page.evaluate('() => document.body.innerText')
            print(f"  Page text length: {len(page_text)} characters")

            with open('debug_skyscanner_text.txt', 'w', encoding='utf-8') as f:
                f.write(page_text)

            # Extract flight data using JavaScript
            flight_data = await self.page.evaluate('''
                () => {
                    const flights = [];
                    const seen = new Set();

                    // Find all price elements
                    const allElements = document.querySelectorAll('*');
                    const priceElements = [];

                    for (const el of allElements) {
                        const text = el.textContent || '';
                        // Match prices like $99, £99, €99, $1,234
                        if (/^\s*[$£€]\s*[\d,]+\s*$/.test(text) && text.length < 15) {
                            priceElements.push(el);
                        }
                    }

                    // For each price, find the parent flight card
                    for (const priceEl of priceElements) {
                        let container = priceEl;

                        // Go up to find the flight card container
                        for (let i = 0; i < 10; i++) {
                            if (container.parentElement) {
                                container = container.parentElement;
                            }

                            const containerText = container.textContent || '';
                            const hasTime = /\d{1,2}:\d{2}/.test(containerText);
                            const hasDuration = /\d+h\s*\d*m?|\d+\s*hr/i.test(containerText);

                            if (hasTime && hasDuration && containerText.length > 50 && containerText.length < 2000) {
                                const price = priceEl.textContent.trim();

                                // Skip duplicates
                                const key = price + containerText.substring(0, 60);
                                if (seen.has(key)) continue;
                                seen.add(key);

                                // Extract times
                                let departureTime = null;
                                let arrivalTime = null;

                                // Try pattern with separator
                                const timeWithSep = containerText.match(/(\d{1,2}:\d{2})\s*[–\-−]\s*(\d{1,2}:\d{2})/);
                                if (timeWithSep) {
                                    departureTime = timeWithSep[1];
                                    arrivalTime = timeWithSep[2];
                                } else {
                                    // Find unique times
                                    const allTimes = containerText.match(/\d{1,2}:\d{2}/g);
                                    if (allTimes && allTimes.length >= 2) {
                                        const uniqueTimes = [...new Set(allTimes)];
                                        if (uniqueTimes.length >= 2) {
                                            departureTime = uniqueTimes[0];
                                            arrivalTime = uniqueTimes[1];
                                        }
                                    }
                                }

                                // Extract duration
                                const durationMatch = containerText.match(/(\d+)h\s*(\d*)m?|(\d+)\s*hr\s*(\d*)\s*m?/i);
                                let duration = null;
                                if (durationMatch) {
                                    const hours = durationMatch[1] || durationMatch[3];
                                    const mins = durationMatch[2] || durationMatch[4] || '0';
                                    duration = `${hours}h ${mins}m`;
                                }

                                // Extract stops
                                let stops = "Unknown";
                                const textLower = containerText.toLowerCase();
                                if (textLower.includes("direct") || textLower.includes("nonstop")) {
                                    stops = "Direct";
                                } else {
                                    const stopMatch = containerText.match(/(\d+)\s*stop/i);
                                    if (stopMatch) {
                                        stops = stopMatch[1] === "1" ? "1 stop" : stopMatch[1] + " stops";
                                    }
                                }

                                // Extract airline
                                const airlineNames = [
                                    'Spirit', 'United', 'Delta', 'American', 'JetBlue',
                                    'Southwest', 'Frontier', 'Alaska', 'LATAM', 'Avianca',
                                    'Copa', 'Aeromexico', 'Air France', 'British Airways',
                                    'Lufthansa', 'Emirates', 'Qatar', 'TAP', 'Iberia',
                                    'Ryanair', 'easyJet', 'Wizz Air', 'Norwegian',
                                    'Sun Country', 'Hawaiian', 'Allegiant', 'Breeze'
                                ];
                                let airline = "Various";
                                for (const name of airlineNames) {
                                    if (containerText.includes(name)) {
                                        airline = name;
                                        break;
                                    }
                                }

                                flights.push({
                                    departure_time: departureTime,
                                    arrival_time: arrivalTime,
                                    duration: duration,
                                    stops: stops,
                                    airline: airline,
                                    price: price,
                                    source: 'Skyscanner'
                                });

                                break;
                            }
                        }
                    }

                    // Sort by price
                    flights.sort((a, b) => {
                        const priceA = parseInt((a.price || '0').replace(/[^\d]/g, '')) || 999999;
                        const priceB = parseInt((b.price || '0').replace(/[^\d]/g, '')) || 999999;
                        return priceA - priceB;
                    });

                    return flights.slice(0, 30);
                }
            ''')

            flights = flight_data if flight_data else []
            print(f"  Extracted {len(flights)} flights")

            if len(flights) == 0:
                print("  ⚠ No flights extracted - check debug_skyscanner.png")
                flights.append({
                    'price': 'Could not extract - check debug files',
                    'departure_time': 'See debug_skyscanner.png',
                    'arrival_time': 'See debug_skyscanner_text.txt',
                    'duration': 'N/A',
                    'stops': 'N/A',
                    'airline': 'N/A',
                    'source': 'Skyscanner',
                    'note': 'Extraction failed'
                })

        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
            flights.append({
                'error': str(e),
                'source': 'Skyscanner',
                'note': 'Try running with headless=False to debug'
            })

        return flights


async def search_skyscanner_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    headless: bool = True
) -> list[dict]:
    """
    Convenience function to search Skyscanner flights.

    Example:
        flights = await search_skyscanner_flights(
            origin="New York",
            destination="Los Angeles",
            departure_date="2025-02-15"
        )
    """
    scraper = SkyscannerScraper(headless=headless)

    try:
        await scraper.start_browser()
        flights = await scraper.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date
        )
        return flights
    finally:
        await scraper.close_browser()


# Test code
if __name__ == "__main__":
    async def test_scraper():
        print("=" * 60)
        print("SKYSCANNER SCRAPER TEST")
        print("=" * 60)

        today = datetime.now()
        departure = today + timedelta(days=14)
        departure_str = departure.strftime('%Y-%m-%d')

        print(f"\nTest search:")
        print(f"  From: New York")
        print(f"  To: Los Angeles")
        print(f"  Departure: {departure_str}")
        print()

        flights = await search_skyscanner_flights(
            origin="New York",
            destination="Los Angeles",
            departure_date=departure_str,
            headless=True
        )

        print("\n" + "=" * 60)
        print("SEARCH RESULTS")
        print("=" * 60)

        if flights:
            for i, flight in enumerate(flights[:10], 1):
                print(f"\nFlight {i}:")
                for key, value in flight.items():
                    print(f"  {key}: {value}")
        else:
            print("\nNo flights found.")

        return flights

    asyncio.run(test_scraper())
