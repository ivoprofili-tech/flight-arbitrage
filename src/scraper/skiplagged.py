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
        # Use 'domcontentloaded' instead of 'networkidle' - Skiplagged keeps making requests
        await self.page.goto(url, wait_until='domcontentloaded', timeout=15000)
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

        # Scroll down to load more results (lazy loading)
        print("[Step 3] Scrolling to load more flights...")
        for _ in range(3):
            await self.page.evaluate('window.scrollBy(0, 500)')
            await self._human_delay(500, 800)

        await self.page.wait_for_timeout(2000)

        print("[Step 4] Extracting flight data...")
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
            # Wait longer for Skiplagged to load flight results
            print("  Waiting for flight cards to appear...")

            # Skiplagged loads results dynamically, wait for price elements
            await self.page.wait_for_timeout(5000)

            # Check if we have any price-like content
            has_prices = await self.page.evaluate('''
                () => {
                    const text = document.body.innerText;
                    return /\$\d+/.test(text);
                }
            ''')

            if has_prices:
                print("  ✓ Found price data on page")
                # Give a bit more time for all results to render
                await self.page.wait_for_timeout(2000)
            else:
                print("  ⚠ No prices found yet, waiting more...")
                await self.page.wait_for_timeout(5000)

        except Exception as e:
            print(f"  ⚠ Error waiting for results: {e}")
            await self.page.wait_for_timeout(5000)

    async def _extract_flights(self) -> list[dict]:
        """Extract flight information from Skiplagged results using hybrid approach."""
        import re
        flights = []

        try:
            # First, try JavaScript DOM extraction for flight rows
            # This captures flights that may not appear in innerText
            js_flights = await self.page.evaluate('''
                () => {
                    const flights = [];
                    const airlines = ["JetBlue", "Delta", "American", "United", "Spirit", "Frontier", "Alaska", "Southwest"];

                    // Find all elements that look like flight rows
                    // Look for elements containing duration patterns like "7h" followed by stops
                    const allDivs = document.querySelectorAll('div');

                    for (const div of allDivs) {
                        const text = div.innerText || "";
                        const lines = text.split("\\n").map(l => l.trim()).filter(l => l);

                        // Check if this div has the flight structure:
                        // Line 0: duration (e.g., "7h")
                        // Line 1: stops (e.g., "nonstop" or "1 stop")
                        // Contains airline, times, price
                        if (lines.length < 5 || lines.length > 25) continue;

                        // Check for duration + stops pattern at start
                        const durMatch = lines[0].match(/^(\\d+h)$/);
                        if (!durMatch) continue;

                        const stopsLine = lines[1].toLowerCase();
                        if (stopsLine !== "nonstop" && !stopsLine.match(/^\\d+\\s*stops?$/)) continue;

                        // Find airline
                        let airline = "Unknown";
                        for (const a of airlines) {
                            if (lines.includes(a)) {
                                airline = a;
                                break;
                            }
                        }

                        // Find price (last $XXX or US$XXX that's not "off")
                        let price = null;
                        for (let i = lines.length - 1; i >= 0; i--) {
                            const priceMatch = lines[i].match(/^(?:US)?\\$(\\d+)$/);
                            if (priceMatch) {
                                price = "$" + priceMatch[1];
                                break;
                            }
                        }
                        if (!price) continue;

                        // Find times - support both 12h (6:00am) and 24h (07:00) formats
                        const times12h = text.match(/(\\d{1,2}:\\d{2}(?:am|pm))/gi) || [];
                        const times24h = lines.filter(l => l.match(/^\\d{2}:\\d{2}$/));
                        const times = times12h.length >= 2 ? times12h : times24h;

                        if (times.length < 2) continue;

                        // Check for skiplagging deal
                        const isSkiplagged = text.toLowerCase().includes("skiplagging");
                        const savingsMatch = text.match(/\\$(\\d+)\\s*off/i);

                        const flight = {
                            airline: airline,
                            departure_time: times[0],
                            arrival_time: times[times.length - 1],
                            duration: durMatch[1],
                            stops: stopsLine === "nonstop" ? "Nonstop" : stopsLine.replace(/stop/, " stop").trim(),
                            price: price,
                            source: "Skiplagged"
                        };

                        if (isSkiplagged) {
                            flight.skiplagged_deal = true;
                            if (savingsMatch) flight.savings = "$" + savingsMatch[1] + " off";
                        }

                        // Use price + times as unique key
                        const key = price + "_" + times[0] + "_" + times[times.length - 1];
                        flight._key = key;

                        flights.push(flight);
                    }

                    // Deduplicate by key
                    const seen = new Set();
                    const unique = [];
                    for (const f of flights) {
                        if (!seen.has(f._key)) {
                            seen.add(f._key);
                            delete f._key;
                            unique.push(f);
                        }
                    }

                    return unique;
                }
            ''')

            if js_flights:
                print(f"  JS DOM extraction found {len(js_flights)} flights")
                flights.extend(js_flights)

            # Also get page text for debugging and fallback parsing
            page_text = await self.page.evaluate('() => document.body.innerText')
            print(f"  Page text length: {len(page_text)} characters")

            with open('debug_skiplagged_text.txt', 'w', encoding='utf-8') as f:
                f.write(page_text)

            # Parse the sequential text to find flight blocks
            # Each flight follows this pattern in the text:
            # Duration (6h or 11h 30m)
            # Stops (nonstop or X stops)
            # Airline
            # Departure time (6:00am)
            # Departure airport (JFK)
            # [optional layover info]
            # Arrival time (9:16am)
            # Arrival airport (LAX)
            # [optional "Skiplagging" and "$XX off"]
            # Price ($209)

            # Text-based fallback parsing (for flights not captured by JS DOM)
            lines = page_text.split('\n')
            airlines = ["JetBlue", "Delta", "American", "United", "Spirit", "Frontier", "Alaska", "Southwest"]

            # Build seen set from JS-extracted flights to avoid duplicates
            seen = set()
            for f in flights:
                key = f"{f['price']}_{f['departure_time']}_{f['arrival_time']}"
                seen.add(key)

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Look for duration pattern (start of a flight block)
                # Duration is like "6h" or "11h" - total flight times
                duration_match = re.match(r'^(\d+h)$', line)

                if duration_match:
                    # CRITICAL: Next line MUST be stops info to confirm this is a flight block
                    # This filters out segment times like "1h 33m" which aren't flight starts
                    if i + 1 >= len(lines):
                        i += 1
                        continue

                    next_line = lines[i + 1].strip().lower()
                    is_stops_line = (
                        next_line == "nonstop" or
                        re.match(r'^\d+\s*stops?$', next_line)
                    )

                    if not is_stops_line:
                        i += 1
                        continue

                    duration = duration_match.group(1)
                    stops = "Nonstop" if next_line == "nonstop" else next_line.replace("stop", " stop").strip()
                    if "1 stop" in stops:
                        stops = "1 stop"
                    elif "stops" not in stops and "stop" in stops:
                        stops = stops  # keep as is
                    else:
                        # Format "2 stops" etc
                        stop_num = re.search(r'(\d+)', stops)
                        if stop_num:
                            n = stop_num.group(1)
                            stops = f"{n} stop" if n == "1" else f"{n} stops"

                    # Collect flight block lines (starting after stops line)
                    block_lines = [line, lines[i + 1].strip()]
                    j = i + 2
                    price = None
                    airline = "Unknown"

                    # Read lines until we find the price
                    while j < len(lines) and j < i + 25:
                        curr_line = lines[j].strip()

                        # Check for airline name (exact match on its own line)
                        for a in airlines:
                            if curr_line == a:
                                airline = a
                                break

                        # Check if this is a standalone price (the actual flight price)
                        # Must be just $XXX or US$XXX with nothing else (not "$XX off")
                        price_match = re.match(r'^(?:US)?\$(\d+)$', curr_line)
                        if price_match:
                            price = f"${price_match.group(1)}"  # Normalize to $XXX format
                            block_lines.append(curr_line)
                            j += 1
                            break

                        # Check if we hit the next flight (duration + stops pattern)
                        if re.match(r'^\d+h$', curr_line):
                            # Peek ahead to see if next line is stops
                            if j + 1 < len(lines):
                                peek = lines[j + 1].strip().lower()
                                if peek == "nonstop" or re.match(r'^\d+\s*stops?$', peek):
                                    break  # This is the next flight

                        block_lines.append(curr_line)
                        j += 1

                    if not price:
                        i += 1
                        continue

                    # Extract times from the block
                    # Supports both 12-hour (6:00am) and 24-hour (07:00, 19:45) formats
                    block_text = '\n'.join(block_lines)
                    # First try 12-hour format
                    times = re.findall(r'(\d{1,2}:\d{2}(?:am|pm))', block_text, re.IGNORECASE)
                    # If no 12-hour times found, try 24-hour format (HH:MM on own line)
                    if len(times) < 2:
                        times = re.findall(r'^(\d{2}:\d{2})$', block_text, re.MULTILINE)

                    # For multi-stop flights, we want first and last times
                    # Filter out intermediate times that are part of layover info
                    if len(times) >= 2:
                        departure_time = times[0]
                        arrival_time = times[-1]

                        # Check for skiplagging deal
                        is_skiplagged = "skiplagging" in block_text.lower()
                        savings_match = re.search(r'\$(\d+)\s*off', block_text, re.IGNORECASE)
                        savings = f"${savings_match.group(1)} off" if savings_match else None

                        # Create unique key to avoid duplicates
                        key = f"{price}_{departure_time}_{arrival_time}"
                        if key not in seen:
                            seen.add(key)

                            flight = {
                                'airline': airline,
                                'departure_time': departure_time,
                                'arrival_time': arrival_time,
                                'duration': duration,
                                'stops': stops,
                                'price': price,
                                'source': 'Skiplagged'
                            }

                            if is_skiplagged:
                                flight['skiplagged_deal'] = True
                                if savings:
                                    flight['savings'] = savings

                            flights.append(flight)

                    i = j  # Move to after the block
                else:
                    i += 1

            # Sort by price
            flights.sort(key=lambda f: int(re.sub(r'\D', '', f['price']) or '99999'))

            text_parsed = len(flights) - len(js_flights) if js_flights else len(flights)
            print(f"  Extracted {len(flights)} total flights ({len(js_flights) if js_flights else 0} from DOM, {text_parsed} from text)")

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
            import traceback
            traceback.print_exc()
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
