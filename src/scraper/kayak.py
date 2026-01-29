"""
Kayak Flight Scraper
====================
This script uses Playwright to automate a web browser and scrape flight data
from Kayak.

Similar to the Google Flights scraper, using form filling to appear more human-like.
"""

import asyncio
import os
import glob
import shutil
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


class KayakScraper:
    """
    A class to scrape flight data from Kayak.
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
        # Clear old videos from previous runs
        self._clear_old_videos()

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
            record_video_size={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York'
        )

        self.page = await self.context.new_page()

        # Add anti-detection scripts
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

        # Rename video with descriptive name
        if video_path and os.path.exists(video_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"videos/kayak_{timestamp}.webm"
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

    async def handle_cookie_consent(self):
        """Handle cookie consent popup on Kayak."""
        try:
            cookie_selectors = [
                'button:has-text("Accept all")',
                'button:has-text("Accept")',
                'button:has-text("I Accept")',
                'button:has-text("OK")',
                '[aria-label="Accept"]',
                '.onetrust-accept-btn-handler',
            ]

            for selector in cookie_selectors:
                try:
                    button = await self.page.wait_for_selector(selector, timeout=1000)
                    if button:
                        await button.click()
                        print("  ✓ Accepted cookies")
                        await self._human_delay(300, 500)
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
        Search for flights on Kayak using manual form filling.

        Args:
            origin: Departure city or airport code
            destination: Arrival city or airport code
            departure_date: Date in YYYY-MM-DD format
            return_date: Optional return date in YYYY-MM-DD format

        Returns:
            List of flight dictionaries
        """
        print(f"\nSearching Kayak: {origin} → {destination}")
        print(f"Departure: {departure_date}" + (f", Return: {return_date}" if return_date else " (one-way)"))

        # Step 1: Open Kayak flights page
        print("\n[Step 1] Opening Kayak...")
        await self.page.goto('https://www.kayak.com/flights', wait_until='networkidle')
        await self._human_delay(1500, 2500)

        # Handle cookie consent
        await self.handle_cookie_consent()

        # Step 2: Set one-way if no return date
        if not return_date:
            print("[Step 2] Setting trip type to one-way...")
            try:
                # Click on trip type dropdown
                trip_selectors = [
                    '[aria-label="Trip type"]',
                    'button:has-text("Round-trip")',
                    'button:has-text("Roundtrip")',
                    '[data-testid="trip-type-selector"]',
                ]

                for selector in trip_selectors:
                    try:
                        btn = await self.page.wait_for_selector(selector, timeout=2000)
                        if btn:
                            await btn.click()
                            print(f"  ✓ Clicked trip type dropdown")
                            await self._human_delay(300, 500)
                            break
                    except:
                        continue

                # Select One-way
                one_way_selectors = [
                    'li:has-text("One-way")',
                    'a:has-text("One-way")',
                    '[data-testid="one-way"]',
                    'div:has-text("One-way")',
                ]

                for selector in one_way_selectors:
                    try:
                        one_way = await self.page.wait_for_selector(selector, timeout=2000)
                        if one_way:
                            await one_way.click()
                            print("  ✓ Selected One-way")
                            await self._human_delay(300, 500)
                            break
                    except:
                        continue

            except Exception as e:
                print(f"  ⚠ Could not set one-way: {e}")
        else:
            print("[Step 2] Keeping round-trip mode...")

        # Step 3: Fill origin field
        print(f"[Step 3] Entering origin: {origin}...")
        try:
            # Click on origin field
            origin_selectors = [
                '[aria-label="Flight origin input"]',
                '[aria-label*="origin"]',
                '[data-testid="origin-input"]',
                'input[placeholder*="From"]',
                'input[name="origin"]',
            ]

            for selector in origin_selectors:
                try:
                    origin_field = await self.page.wait_for_selector(selector, timeout=2000)
                    if origin_field:
                        await origin_field.click()
                        print("  ✓ Clicked origin field")
                        await self._human_delay(200, 400)
                        break
                except:
                    continue

            # Clear and type origin
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.type(origin, delay=random.randint(50, 100))
            await self._human_delay(800, 1200)

            # Select from dropdown
            try:
                suggestion = await self.page.wait_for_selector(
                    'ul li:first-child, [role="option"]:first-child',
                    timeout=3000
                )
                if suggestion:
                    await suggestion.click()
                    print(f"  ✓ Selected {origin}")
            except:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for {origin}")

            await self._human_delay(300, 500)

        except Exception as e:
            print(f"  ⚠ Error setting origin: {e}")

        # Step 4: Fill destination field
        print(f"[Step 4] Entering destination: {destination}...")
        try:
            # Click on destination field
            dest_selectors = [
                '[aria-label="Flight destination input"]',
                '[aria-label*="destination"]',
                '[data-testid="destination-input"]',
                'input[placeholder*="To"]',
                'input[name="destination"]',
            ]

            for selector in dest_selectors:
                try:
                    dest_field = await self.page.wait_for_selector(selector, timeout=2000)
                    if dest_field:
                        await dest_field.click()
                        print("  ✓ Clicked destination field")
                        await self._human_delay(200, 400)
                        break
                except:
                    continue

            # Type destination
            await self.page.keyboard.type(destination, delay=random.randint(50, 100))
            await self._human_delay(800, 1200)

            # Select from dropdown
            try:
                suggestion = await self.page.wait_for_selector(
                    'ul li:first-child, [role="option"]:first-child',
                    timeout=3000
                )
                if suggestion:
                    await suggestion.click()
                    print(f"  ✓ Selected {destination}")
            except:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for {destination}")

            await self._human_delay(300, 500)

        except Exception as e:
            print(f"  ⚠ Error setting destination: {e}")

        # Step 5: Set departure date
        print(f"[Step 5] Setting departure date: {departure_date}...")
        try:
            # Click on date field
            date_selectors = [
                '[aria-label*="Departure"]',
                '[aria-label*="Start date"]',
                '[data-testid="depart-input"]',
                'input[placeholder*="Depart"]',
            ]

            for selector in date_selectors:
                try:
                    date_field = await self.page.wait_for_selector(selector, timeout=2000)
                    if date_field:
                        await date_field.click()
                        print("  ✓ Clicked date field")
                        await self._human_delay(500, 800)
                        break
                except:
                    continue

            # Parse target date
            target_date = datetime.strptime(departure_date, '%Y-%m-%d')
            day = target_date.day
            month_name = target_date.strftime('%B')

            # Try to click the specific date
            date_cell_selectors = [
                f'[aria-label*="{month_name} {day}"]',
                f'[aria-label*="{day}"][aria-label*="{month_name}"]',
                f'[data-day="{day}"]',
            ]

            for selector in date_cell_selectors:
                try:
                    date_cell = await self.page.wait_for_selector(selector, timeout=2000)
                    if date_cell:
                        await date_cell.click()
                        print(f"  ✓ Selected date: {departure_date}")
                        break
                except:
                    continue

            await self._human_delay(300, 500)

        except Exception as e:
            print(f"  ⚠ Error setting date: {e}")

        # Step 6: Click Search button
        print("[Step 6] Clicking Search...")
        try:
            search_selectors = [
                'button[aria-label="Search"]',
                'button:has-text("Search")',
                '[data-testid="search-button"]',
                'button[type="submit"]',
            ]

            for selector in search_selectors:
                try:
                    search_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if search_btn:
                        await search_btn.click()
                        print("  ✓ Clicked Search button")
                        break
                except:
                    continue

        except Exception as e:
            print(f"  ⚠ Error clicking search: {e}")

        # Step 7: Wait for results to load
        print("[Step 7] Waiting for flight results...")
        await self.page.wait_for_timeout(5000)
        await self.page.screenshot(path='debug_kayak_after_search.png')
        await self._wait_for_results()

        # Step 8: Extract flight data
        print("[Step 8] Extracting flight data...")
        await self.page.screenshot(path='debug_kayak.png')
        flights = await self._extract_flights()

        print(f"\nFound {len(flights)} flights on Kayak!")
        return flights

    async def _wait_for_results(self):
        """Wait for Kayak results to load."""
        try:
            # Wait for flight results container
            result_selectors = [
                '[data-testid="flight-card"]',
                '[class*="resultWrapper"]',
                '[class*="flightResult"]',
                '.nrc6',  # Kayak's result class
                'div[class*="result"]',
            ]

            for selector in result_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=15000)
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
        """Extract flight information from Kayak results."""
        flights = []

        try:
            # Save page text for debugging
            page_text = await self.page.evaluate('() => document.body.innerText')
            print(f"  Page text length: {len(page_text)} characters")

            with open('debug_kayak_text.txt', 'w', encoding='utf-8') as f:
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
                        // Match prices like $99, $1,234
                        if (/^\s*\$\s*[\d,]+\s*$/.test(text) && text.length < 15) {
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
                            const hasTime = /\d{1,2}:\d{2}\s*(am|pm|AM|PM)?/.test(containerText);
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
                                const timeWithSep = containerText.match(/(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)\s*[–\-−]\s*(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?)/i);
                                if (timeWithSep) {
                                    departureTime = timeWithSep[1].trim();
                                    arrivalTime = timeWithSep[2].trim();
                                } else {
                                    // Find unique times
                                    const allTimes = containerText.match(/\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?/gi);
                                    if (allTimes && allTimes.length >= 2) {
                                        const uniqueTimes = [...new Set(allTimes.map(t => t.trim()))];
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
                                if (textLower.includes("nonstop") || textLower.includes("non-stop") || textLower.includes("direct")) {
                                    stops = "Nonstop";
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
                                    source: 'Kayak'
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
                print("  ⚠ No flights extracted - check debug_kayak.png")
                flights.append({
                    'price': 'Could not extract - check debug files',
                    'departure_time': 'See debug_kayak.png',
                    'arrival_time': 'See debug_kayak_text.txt',
                    'duration': 'N/A',
                    'stops': 'N/A',
                    'airline': 'N/A',
                    'source': 'Kayak',
                    'note': 'Extraction failed'
                })

        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
            flights.append({
                'error': str(e),
                'source': 'Kayak',
                'note': 'Try running with headless=False to debug'
            })

        return flights


async def search_kayak_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    headless: bool = True
) -> list[dict]:
    """
    Convenience function to search Kayak flights.

    Example:
        flights = await search_kayak_flights(
            origin="New York",
            destination="Los Angeles",
            departure_date="2025-02-15"
        )
    """
    scraper = KayakScraper(headless=headless)

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
        print("KAYAK SCRAPER TEST")
        print("=" * 60)

        today = datetime.now()
        departure = today + timedelta(days=14)
        departure_str = departure.strftime('%Y-%m-%d')

        print(f"\nTest search:")
        print(f"  From: New York")
        print(f"  To: Los Angeles")
        print(f"  Departure: {departure_str}")
        print()

        flights = await search_kayak_flights(
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
