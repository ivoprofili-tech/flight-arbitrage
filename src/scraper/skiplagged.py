"""
Skiplagged Flight Scraper
=========================
This script uses Playwright to automate a web browser and scrape flight data
from Skiplagged.

Skiplagged is known for finding "hidden city" fares - flights where it's cheaper
to book a connecting flight and skip the last leg.
"""

import asyncio
import os
import glob
import shutil
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class SkiplaggedScraper:
    """
    A class to scrape flight data from Skiplagged.
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
        self._clear_old_videos()

        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )

        os.makedirs('videos', exist_ok=True)

        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            record_video_dir='videos/',
            record_video_size={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )

        self.page = await self.context.new_page()

        await self.page.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        ''')

        print("Browser started! Video recording enabled (saves to videos/ folder)")

    def _clear_old_videos(self):
        """Remove old video files from previous runs."""
        if os.path.exists('videos'):
            old_videos = glob.glob('videos/*.webm')
            for video in old_videos:
                try:
                    os.remove(video)
                except:
                    pass
            if old_videos:
                print(f"Cleared {len(old_videos)} old video(s) from videos/ folder")

    async def _human_delay(self, min_ms=200, max_ms=600):
        """Add a random human-like delay between actions."""
        delay = random.randint(min_ms, max_ms)
        await self.page.wait_for_timeout(delay)

    async def close_browser(self):
        """Clean up: close the browser and save the video with descriptive name."""
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

        if video_path and os.path.exists(video_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"videos/skiplagged_{timestamp}.webm"
            try:
                shutil.move(video_path, new_name)
                video_path = new_name
            except:
                pass

            print(f"\n{'='*50}")
            print(f"VIDEO SAVED: {video_path}")
            print(f"{'='*50}")
            print("Download this file to watch the scraping session")
        else:
            print("Browser closed (no video saved).")

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = None
    ) -> list[dict]:
        """
        Search for flights on Skiplagged.

        Skiplagged uses a simple URL structure that we can navigate to directly.

        Args:
            origin: Departure city or airport code (e.g., "JFK", "LAX")
            destination: Arrival city or airport code
            departure_date: Date in YYYY-MM-DD format
            return_date: Optional return date in YYYY-MM-DD format

        Returns:
            List of flight dictionaries
        """
        print(f"\nSearching Skiplagged: {origin} → {destination}")
        print(f"Departure: {departure_date}" + (f", Return: {return_date}" if return_date else " (one-way)"))

        # Convert city names to airport codes if needed
        origin_code = self._get_airport_code(origin)
        dest_code = self._get_airport_code(destination)

        # Build Skiplagged URL
        # Format: https://skiplagged.com/flights/JFK/LAX/2025-03-01
        if return_date:
            url = f"https://skiplagged.com/flights/{origin_code}/{dest_code}/{departure_date}/{return_date}"
        else:
            url = f"https://skiplagged.com/flights/{origin_code}/{dest_code}/{departure_date}"

        print(f"\n[Step 1] Opening Skiplagged: {url}")
        await self.page.goto(url, wait_until='networkidle')
        await self._human_delay(2000, 3000)

        # Take a screenshot to see what we got
        await self.page.screenshot(path='debug_skiplagged_initial.png')

        # Check for any blocking page
        page_text = await self.page.evaluate('() => document.body.innerText')

        if 'robot' in page_text.lower() or 'captcha' in page_text.lower() or 'verify' in page_text.lower():
            print("  ⚠ Bot detection page detected")
            await self.page.screenshot(path='debug_skiplagged_blocked.png')
            return [{
                'error': 'Bot detection triggered',
                'source': 'Skiplagged',
                'note': 'Check debug_skiplagged_blocked.png'
            }]

        print("[Step 2] Waiting for flight results...")
        await self._wait_for_results()

        print("[Step 3] Extracting flight data...")
        await self.page.screenshot(path='debug_skiplagged.png')
        flights = await self._extract_flights()

        print(f"\nFound {len(flights)} flights on Skiplagged!")
        return flights

    def _get_airport_code(self, location: str) -> str:
        """Convert city name to airport code."""
        # Common city to airport mappings
        city_codes = {
            'new york': 'JFK',
            'nyc': 'JFK',
            'los angeles': 'LAX',
            'la': 'LAX',
            'chicago': 'ORD',
            'san francisco': 'SFO',
            'miami': 'MIA',
            'boston': 'BOS',
            'seattle': 'SEA',
            'denver': 'DEN',
            'atlanta': 'ATL',
            'dallas': 'DFW',
            'houston': 'IAH',
            'phoenix': 'PHX',
            'las vegas': 'LAS',
            'orlando': 'MCO',
            'washington': 'DCA',
            'philadelphia': 'PHL',
            'detroit': 'DTW',
            'minneapolis': 'MSP',
            'tampa': 'TPA',
            'portland': 'PDX',
            'austin': 'AUS',
            'nashville': 'BNA',
            'san diego': 'SAN',
            'charlotte': 'CLT',
            'newark': 'EWR',
            'london': 'LHR',
            'paris': 'CDG',
            'tokyo': 'NRT',
            'cancun': 'CUN',
        }

        location_lower = location.lower().strip()

        # If it's already a 3-letter code, use it directly
        if len(location) == 3 and location.isupper():
            return location

        # Try to find in our mapping
        if location_lower in city_codes:
            return city_codes[location_lower]

        # Default: return uppercase of first 3 chars or the input
        return location.upper()[:3] if len(location) >= 3 else location.upper()

    async def _wait_for_results(self):
        """Wait for Skiplagged results to load."""
        try:
            result_selectors = [
                '[class*="flight"]',
                '[class*="result"]',
                '[class*="itinerary"]',
                'div[data-flight]',
                '.trip-container',
            ]

            for selector in result_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=15000)
                    print("  ✓ Results loaded")
                    await self.page.wait_for_timeout(2000)
                    return
                except PlaywrightTimeout:
                    continue

            print("  ⚠ Could not detect results container, waiting...")
            await self.page.wait_for_timeout(5000)

        except Exception as e:
            print(f"  ⚠ Error waiting for results: {e}")
            await self.page.wait_for_timeout(5000)

    async def _extract_flights(self) -> list[dict]:
        """Extract flight information from Skiplagged results."""
        flights = []

        try:
            page_text = await self.page.evaluate('() => document.body.innerText')
            print(f"  Page text length: {len(page_text)} characters")

            with open('debug_skiplagged_text.txt', 'w', encoding='utf-8') as f:
                f.write(page_text)

            flight_data = await self.page.evaluate('''
                () => {
                    const flights = [];
                    const seen = new Set();

                    const allElements = document.querySelectorAll('*');
                    const priceElements = [];

                    for (const el of allElements) {
                        const text = el.textContent || '';
                        if (/^\s*\$\s*[\d,]+\s*$/.test(text) && text.length < 15) {
                            priceElements.push(el);
                        }
                    }

                    for (const priceEl of priceElements) {
                        let container = priceEl;

                        for (let i = 0; i < 12; i++) {
                            if (container.parentElement) {
                                container = container.parentElement;
                            }

                            const containerText = container.textContent || '';
                            const hasTime = /\d{1,2}:\d{2}\s*(am|pm|AM|PM)?/.test(containerText);
                            const hasDuration = /\d+h\s*\d*m?|\d+\s*hr/i.test(containerText);

                            if (hasTime && hasDuration && containerText.length > 40 && containerText.length < 3000) {
                                const price = priceEl.textContent.trim();

                                const key = price + containerText.substring(0, 80);
                                if (seen.has(key)) continue;
                                seen.add(key);

                                let departureTime = null;
                                let arrivalTime = null;

                                const timeWithSep = containerText.match(/(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)\s*[–\-−→]\s*(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)/i);
                                if (timeWithSep) {
                                    departureTime = timeWithSep[1].trim();
                                    arrivalTime = timeWithSep[2].trim();
                                } else {
                                    const allTimes = containerText.match(/\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?/gi);
                                    if (allTimes && allTimes.length >= 2) {
                                        const uniqueTimes = [...new Set(allTimes.map(t => t.trim()))];
                                        if (uniqueTimes.length >= 2) {
                                            departureTime = uniqueTimes[0];
                                            arrivalTime = uniqueTimes[1];
                                        }
                                    }
                                }

                                const durationMatch = containerText.match(/(\d+)h\s*(\d*)m?|(\d+)\s*hr\s*(\d*)\s*m?/i);
                                let duration = null;
                                if (durationMatch) {
                                    const hours = durationMatch[1] || durationMatch[3];
                                    const mins = durationMatch[2] || durationMatch[4] || '0';
                                    duration = `${hours}h ${mins}m`;
                                }

                                let stops = "Unknown";
                                const textLower = containerText.toLowerCase();
                                if (textLower.includes("nonstop") || textLower.includes("non-stop") || textLower.includes("direct")) {
                                    stops = "Nonstop";
                                } else {
                                    const stopMatch = containerText.match(/(\d+)\s*stop/i);
                                    if (stopMatch) {
                                        stops = stopMatch[1] === "1" ? "1 stop" : stopMatch[1] + " stops";
                                    }
                                }

                                const airlineNames = [
                                    'Spirit', 'United', 'Delta', 'American', 'JetBlue',
                                    'Southwest', 'Frontier', 'Alaska', 'LATAM', 'Avianca',
                                    'Copa', 'Aeromexico', 'Air France', 'British Airways',
                                    'Lufthansa', 'Emirates', 'Qatar', 'TAP', 'Iberia',
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
                                    source: 'Skiplagged'
                                });

                                break;
                            }
                        }
                    }

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
                print("  ⚠ No flights extracted - check debug_skiplagged.png")
                flights.append({
                    'price': 'Could not extract - check debug files',
                    'departure_time': 'See debug_skiplagged.png',
                    'arrival_time': 'See debug_skiplagged_text.txt',
                    'duration': 'N/A',
                    'stops': 'N/A',
                    'airline': 'N/A',
                    'source': 'Skiplagged',
                    'note': 'Extraction failed'
                })

        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
            flights.append({
                'error': str(e),
                'source': 'Skiplagged',
                'note': 'Try running with headless=False to debug'
            })

        return flights


async def search_skiplagged_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    headless: bool = True
) -> list[dict]:
    """
    Convenience function to search Skiplagged flights.

    Example:
        flights = await search_skiplagged_flights(
            origin="JFK",
            destination="LAX",
            departure_date="2025-02-15"
        )
    """
    scraper = SkiplaggedScraper(headless=headless)

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


if __name__ == "__main__":
    async def test_scraper():
        print("=" * 60)
        print("SKIPLAGGED SCRAPER TEST")
        print("=" * 60)

        today = datetime.now()
        departure = today + timedelta(days=14)
        departure_str = departure.strftime('%Y-%m-%d')

        print(f"\nTest search:")
        print(f"  From: JFK")
        print(f"  To: LAX")
        print(f"  Departure: {departure_str}")
        print()

        flights = await search_skiplagged_flights(
            origin="JFK",
            destination="LAX",
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
