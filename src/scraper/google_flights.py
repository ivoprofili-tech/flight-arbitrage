"""
Google Flights Scraper
======================
This script uses Playwright to automate a web browser and scrape flight data
from Google Flights.

KEY CONCEPTS:
- Web scraping: Extracting data from websites programmatically
- Browser automation: Controlling a browser with code (clicking, typing, etc.)
- Selectors: Ways to identify elements on a page (like CSS selectors)
- Async/await: A way to handle operations that take time (like loading pages)
"""

# ============================================================================
# IMPORTS
# ============================================================================
# 'asyncio' lets us run asynchronous code (code that waits for things)
import asyncio

# 'datetime' and 'timedelta' help us work with dates
from datetime import datetime, timedelta

# Playwright is our browser automation library
# - async_playwright: The main entry point for async Playwright
# - TimeoutError: Raised when an operation takes too long
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout


# ============================================================================
# MAIN SCRAPER CLASS
# ============================================================================
class GoogleFlightsScraper:
    """
    A class to scrape flight data from Google Flights.

    Why use a class? It keeps related code organized and lets us maintain
    state (like the browser instance) across multiple operations.
    """

    def __init__(self, headless: bool = True):
        """
        Initialize the scraper.

        Args:
            headless: If True, browser runs invisibly in background.
                      If False, you can watch the browser do its thing!
                      Set to False when debugging to see what's happening.
        """
        self.headless = headless
        self.browser = None
        self.page = None
        self.context = None

    async def start_browser(self):
        """
        Launch the browser with video recording enabled.

        We use Chromium (Chrome's open-source base) because it works well
        with Playwright and is what most people use for scraping.
        """
        # Create a Playwright instance
        self.playwright = await async_playwright().start()

        # Launch the browser
        # - headless: Whether to show the browser window
        # - args: Extra settings for the browser
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']  # Helps avoid detection
        )

        # Create a browser context with video recording enabled
        # Videos are saved to the 'videos' directory
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            record_video_dir='videos/',  # Directory to save videos
            record_video_size={'width': 1280, 'height': 800}
        )

        # Create a new page (like a browser tab)
        self.page = await self.context.new_page()

        print("Browser started successfully! (Video recording enabled)")

    async def close_browser(self):
        """Clean up: close the browser and save the video."""
        video_path = None

        # Get the video path before closing
        if self.page:
            try:
                video = self.page.video
                if video:
                    video_path = await video.path()
            except:
                pass

        # Close context first to ensure video is saved
        if self.context:
            await self.context.close()

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        if video_path:
            print(f"Browser closed. Video saved to: {video_path}")
        else:
            print("Browser closed.")

    async def handle_cookie_consent(self):
        """
        Handle the cookie consent popup that appears in many countries.

        Google shows different popups depending on your location.
        We try to find and click common "Accept" or "Reject" buttons.
        """
        try:
            # Wait a moment for any popup to appear
            await self.page.wait_for_timeout(2000)  # 2000ms = 2 seconds

            # Try different selectors for cookie buttons
            # Selectors are like addresses that help us find elements on the page
            cookie_selectors = [
                'button:has-text("Accept all")',      # English
                'button:has-text("Accept")',          # Shorter version
                'button:has-text("Reject all")',      # Privacy-friendly option
                'button:has-text("I agree")',         # Alternative text
                '[aria-label="Accept all"]',          # Using aria-label attribute
            ]

            for selector in cookie_selectors:
                try:
                    # Check if this button exists (wait max 1 second)
                    button = await self.page.wait_for_selector(selector, timeout=1000)
                    if button:
                        await button.click()
                        print(f"Clicked cookie consent button: {selector}")
                        await self.page.wait_for_timeout(1000)
                        return True
                except PlaywrightTimeout:
                    # Button not found, try the next one
                    continue

            print("No cookie popup found (or already handled)")
            return False

        except Exception as e:
            print(f"Cookie handling note: {e}")
            return False

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = None
    ) -> list[dict]:
        """
        Search for flights on Google Flights.

        Steps:
        1. Open Google Flights
        2. Set one-way if no return date (MUST be before date selection!)
        3. Click the "from" field and type origin
        4. Click the "to" field and type destination
        5. Click date field, select date, click Done
        6. Click Search
        """
        print(f"\nSearching flights: {origin} → {destination}")
        print(f"Departure: {departure_date}" + (f", Return: {return_date}" if return_date else " (one-way)"))

        # Step 1: Open Google Flights
        print("\n[Step 1] Opening Google Flights...")
        await self.page.goto('https://www.google.com/travel/flights', wait_until='networkidle')
        await self.page.wait_for_timeout(2000)

        # Handle cookie consent if needed
        await self.handle_cookie_consent()
        await self.page.screenshot(path='debug_step1.png')

        # Step 2: Set one-way if no return date
        # IMPORTANT: Must set trip type BEFORE selecting dates!
        # Round trip mode expects 2 dates before showing "Done" button
        if not return_date:
            print("[Step 2] Setting trip type to one-way...")
            try:
                # Click on the trip type dropdown (shows "Round trip" by default)
                trip_selectors = [
                    'div[aria-label*="trip"] button',
                    'button:has-text("Round trip")',
                    '[role="button"]:has-text("Round trip")',
                    '//button[contains(., "Round trip")]',
                    '//div[contains(@aria-label, "trip")]//button',
                ]

                trip_clicked = False
                for selector in trip_selectors:
                    try:
                        if selector.startswith('//'):
                            trip_dropdown = await self.page.wait_for_selector(f'xpath={selector}', timeout=1500)
                        else:
                            trip_dropdown = await self.page.wait_for_selector(selector, timeout=1500)
                        if trip_dropdown:
                            await trip_dropdown.click()
                            trip_clicked = True
                            print(f"  ✓ Clicked trip type dropdown")
                            break
                    except:
                        continue

                if trip_clicked:
                    await self.page.wait_for_timeout(500)
                    # Select "One way" from dropdown
                    one_way_selectors = [
                        'li:has-text("One way")',
                        '[role="option"]:has-text("One way")',
                        '//li[contains(., "One way")]',
                    ]
                    for selector in one_way_selectors:
                        try:
                            if selector.startswith('//'):
                                one_way = await self.page.wait_for_selector(f'xpath={selector}', timeout=1500)
                            else:
                                one_way = await self.page.wait_for_selector(selector, timeout=1500)
                            if one_way:
                                await one_way.click()
                                print("  ✓ Set to one-way")
                                break
                        except:
                            continue
                    await self.page.wait_for_timeout(500)
            except Exception as e:
                print(f"  ⚠ Could not set one-way: {e}")

            await self.page.screenshot(path='debug_step2_oneway.png')

        # Step 3: Click the "from" field and enter origin
        print(f"[Step 3] Clicking 'from' field and entering {origin}...")
        try:
            # The origin field shows the auto-detected city (e.g., "San Francisco")
            # We need to click on it - it's the first input/combobox area
            from_field = await self.page.query_selector('input[aria-label*="Where from"], input[placeholder*="Where from"]')
            if from_field:
                await from_field.click()
            else:
                # Try clicking on the displayed city text in the first combobox
                await self.page.click('div[role="combobox"]:first-of-type')

            await self.page.wait_for_timeout(500)

            # Clear existing text and type new origin
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.type(origin, delay=100)
            await self.page.wait_for_timeout(1500)

            await self.page.screenshot(path='debug_step3_typed.png')

            # Select from dropdown - click first suggestion or press Enter
            try:
                suggestion = await self.page.wait_for_selector('ul[role="listbox"] li:first-child', timeout=2000)
                if suggestion:
                    await suggestion.click()
                    print(f"  ✓ Selected {origin} from dropdown")
            except:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for {origin}")

            await self.page.wait_for_timeout(1000)
        except Exception as e:
            print(f"  ⚠ Error setting origin: {e}")

        await self.page.screenshot(path='debug_step3.png')

        # Step 4: Click the "to" field and enter destination
        print(f"[Step 4] Clicking 'to' field and entering {destination}...")
        try:
            # The destination field shows "Where to?"
            to_field = await self.page.query_selector('input[aria-label*="Where to"], input[placeholder*="Where to"]')
            if to_field:
                await to_field.click()
            else:
                # Try clicking on "Where to?" text
                await self.page.click('text="Where to?"')

            await self.page.wait_for_timeout(500)

            # Type destination
            await self.page.keyboard.type(destination, delay=100)
            await self.page.wait_for_timeout(1500)

            await self.page.screenshot(path='debug_step4_typed.png')

            # Select from dropdown
            try:
                suggestion = await self.page.wait_for_selector('ul[role="listbox"] li:first-child', timeout=2000)
                if suggestion:
                    await suggestion.click()
                    print(f"  ✓ Selected {destination} from dropdown")
            except:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for {destination}")

            await self.page.wait_for_timeout(1000)
        except Exception as e:
            print(f"  ⚠ Error setting destination: {e}")

        await self.page.screenshot(path='debug_step4.png')

        # Step 5: Click date field, select date, click Done
        print(f"[Step 5] Setting departure date: {departure_date}...")
        try:
            # Click on the departure date field
            date_field = await self.page.query_selector('input[aria-label*="Departure"], div[data-placeholder="Departure"]')
            if date_field:
                await date_field.click()
            else:
                await self.page.click('text="Departure"')

            await self.page.wait_for_timeout(1000)

            # Parse date and find the right cell
            target_date = datetime.strptime(departure_date, '%Y-%m-%d')
            day = target_date.day
            month_name = target_date.strftime('%B')

            # Try to click the specific date
            date_selectors = [
                f'[aria-label*="{month_name} {day}"]',
                f'[data-iso="{departure_date}"]',
            ]

            for selector in date_selectors:
                try:
                    date_cell = await self.page.wait_for_selector(selector, timeout=2000)
                    if date_cell:
                        await date_cell.click()
                        print(f"  ✓ Selected date: {departure_date}")
                        break
                except:
                    continue

            await self.page.wait_for_timeout(500)

            # Click Done button - try multiple approaches
            done_clicked = False
            done_selectors = [
                'button[aria-label="Done"]',
                'button:has-text("Done")',
                'span:has-text("Done")',
                '[aria-label="Done"]',
                'button.VfPpkd-LgbsSe:has-text("Done")',  # Material Design button
                '//button[.//span[text()="Done"]]',  # XPath for button containing span with Done
                '//span[text()="Done"]/ancestor::button',  # XPath: find span, go up to button
            ]

            for selector in done_selectors:
                try:
                    if selector.startswith('//'):
                        # Use XPath
                        done_btn = await self.page.wait_for_selector(f'xpath={selector}', timeout=1500)
                    else:
                        done_btn = await self.page.wait_for_selector(selector, timeout=1500)

                    if done_btn:
                        # Make sure button is visible and clickable
                        await done_btn.scroll_into_view_if_needed()
                        await self.page.wait_for_timeout(200)
                        await done_btn.click()
                        done_clicked = True
                        print(f"  ✓ Clicked Done button with: {selector}")
                        break
                except Exception:
                    continue

            # If no Done button found, try pressing Escape or clicking outside
            if not done_clicked:
                print("  ⚠ Done button not found, trying alternatives...")
                try:
                    # Try pressing Escape to close the date picker
                    await self.page.keyboard.press('Escape')
                    print("  ✓ Pressed Escape to close date picker")
                except:
                    pass

            await self.page.wait_for_timeout(1000)
        except Exception as e:
            print(f"  ⚠ Error setting date: {e}")

        await self.page.screenshot(path='debug_step5.png')

        # Step 6: Click Search
        print("[Step 6] Clicking Search...")
        try:
            search_btn = await self.page.query_selector('button:has-text("Search")')
            if search_btn:
                await search_btn.click()
                print("  ✓ Clicked Search button")
            else:
                # Try Explore button as fallback
                explore_btn = await self.page.query_selector('button:has-text("Explore")')
                if explore_btn:
                    await explore_btn.click()
                    print("  ✓ Clicked Explore button")
                else:
                    await self.page.keyboard.press('Enter')
                    print("  ✓ Pressed Enter")
        except Exception as e:
            print(f"  ⚠ Error clicking search: {e}")

        # Wait for results to load
        print("[Step 7] Waiting for results...")
        await self.page.wait_for_timeout(5000)
        await self.page.screenshot(path='debug_step7_results.png')

        current_url = self.page.url
        print(f"  Current URL: {current_url[:80]}...")

        # Wait for flight results
        await self._wait_for_results()

        # Extract flight data
        print("[Step 8] Extracting flight data...")
        await self.page.screenshot(path='debug_screenshot.png')
        flights = await self._extract_flights()

        print(f"\nFound {len(flights)} flights!")
        return flights

    async def _fill_location_field(self, is_origin: bool, location: str):
        """
        Fill in the origin or destination field.

        This is tricky because Google Flights uses dynamic input fields
        that change as you type. We need to:
        1. Click the field to activate it
        2. Clear any existing text
        3. Type the new location
        4. Wait for suggestions
        5. Click on the first suggestion
        """
        try:
            # Google Flights has input fields we need to click first
            if is_origin:
                # For origin, click on the first input area
                selectors = [
                    'div[data-placeholder="Where from?"]',
                    'input[placeholder="Where from?"]',
                    'input[aria-label="Where from?"]',
                    '[aria-label="Where from?"]',
                ]
            else:
                # For destination, click on the "Where to?" area
                selectors = [
                    'div[data-placeholder="Where to?"]',
                    'input[placeholder="Where to?"]',
                    'input[aria-label="Where to?"]',
                    '[aria-label="Where to?"]',
                    'div[class*="destination"]',
                ]

            clicked = False
            for selector in selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        clicked = True
                        print(f"  Clicked: {selector}")
                        break
                except PlaywrightTimeout:
                    continue

            if not clicked:
                print(f"  ⚠ Could not find {'origin' if is_origin else 'destination'} field, trying Tab key")
                # Try tabbing to the field
                if not is_origin:
                    await self.page.keyboard.press('Tab')

            await self.page.wait_for_timeout(500)

            # Clear any existing text
            await self.page.keyboard.press('Control+a')
            await self.page.wait_for_timeout(100)

            # Type the location slowly for autocomplete to work
            await self.page.keyboard.type(location, delay=150)
            print(f"  Typed: {location}")

            # Wait for autocomplete suggestions to appear
            await self.page.wait_for_timeout(2000)

            # Try to click on the first suggestion in the dropdown
            suggestion_selectors = [
                'ul[role="listbox"] li:first-child',
                'li[data-ved]:first-child',
                '[role="option"]:first-child',
                'div[class*="suggestion"]:first-child',
            ]

            suggestion_clicked = False
            for selector in suggestion_selectors:
                try:
                    suggestion = await self.page.wait_for_selector(selector, timeout=2000)
                    if suggestion:
                        await suggestion.click()
                        suggestion_clicked = True
                        print(f"  ✓ Selected suggestion for: {location}")
                        break
                except PlaywrightTimeout:
                    continue

            # If no suggestion clicked, press Enter
            if not suggestion_clicked:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for: {location}")

            await self.page.wait_for_timeout(1000)

        except Exception as e:
            print(f"  ⚠ Could not fill location field: {e}")

    async def _fill_date_field(self, date_str: str, is_departure: bool):
        """
        Fill in the date field.

        Google Flights has a date picker that we need to interact with.
        This is one of the trickier parts of scraping - date pickers
        vary a lot between websites.
        """
        try:
            # Click on the date field area
            date_selectors = [
                '[data-placeholder="Departure"]' if is_departure else '[data-placeholder="Return"]',
                '[aria-label="Departure"]' if is_departure else '[aria-label="Return"]',
                'input[placeholder="Departure"]' if is_departure else 'input[placeholder="Return"]',
                '[class*="date"]',
            ]

            clicked = False
            for selector in date_selectors:
                try:
                    date_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if date_input:
                        await date_input.click()
                        clicked = True
                        print(f"  Clicked date field: {selector}")
                        break
                except PlaywrightTimeout:
                    continue

            if not clicked:
                print("  ⚠ Could not find date field")
                return

            await self.page.wait_for_timeout(1000)

            # Parse the target date
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            day = target_date.day
            month_name = target_date.strftime('%B')  # Full month name (e.g., "March")
            month_short = target_date.strftime('%b')  # Short month (e.g., "Mar")

            # Try multiple selector patterns for the date cell
            date_cell_selectors = [
                f'[data-iso="{date_str}"]',
                f'[aria-label*="{month_name} {day}"]',
                f'[aria-label*="{month_short} {day}"]',
                f'[aria-label*="{day}"][aria-label*="{month_name}"]',
            ]

            date_selected = False
            for selector in date_cell_selectors:
                try:
                    date_cell = await self.page.wait_for_selector(selector, timeout=2000)
                    if date_cell:
                        await date_cell.click()
                        date_selected = True
                        print(f"  ✓ Selected date: {date_str}")
                        break
                except PlaywrightTimeout:
                    continue

            if not date_selected:
                print(f"  ⚠ Could not find date {date_str} in calendar")

            await self.page.wait_for_timeout(500)

            # Click "Done" button if present
            done_selectors = [
                'button:has-text("Done")',
                'button:has-text("OK")',
                'button:has-text("Apply")',
                '[aria-label="Done"]',
            ]

            for selector in done_selectors:
                try:
                    done_btn = await self.page.wait_for_selector(selector, timeout=1500)
                    if done_btn:
                        await done_btn.click()
                        print("  ✓ Clicked Done button")
                        break
                except PlaywrightTimeout:
                    continue

            await self.page.wait_for_timeout(500)

        except Exception as e:
            print(f"  ⚠ Could not fill date field: {e}")

    async def _click_search(self):
        """Click the search button to find flights."""
        try:
            # Save a debug screenshot before searching
            await self.page.screenshot(path='debug_before_search.png')
            print("  Screenshot saved: debug_before_search.png")

            # Look for the search button with various selectors
            search_selectors = [
                'button:has-text("Search")',
                'button:has-text("Explore")',
                'button:has-text("Buscar")',  # Spanish
                'button:has-text("Pesquisar")',  # Portuguese
                '[aria-label="Search"]',
                '[aria-label*="Search"]',
                'button[jsname="vLv7Lb"]',  # Google's internal button name
            ]

            for selector in search_selectors:
                try:
                    search_btn = await self.page.wait_for_selector(selector, timeout=2000)
                    if search_btn:
                        await search_btn.click()
                        print(f"  ✓ Clicked search button: {selector}")
                        return
                except PlaywrightTimeout:
                    continue

            # If no search button found, try pressing Enter
            await self.page.keyboard.press('Enter')
            print("  ✓ Pressed Enter to search")

        except Exception as e:
            print(f"  ⚠ Search button issue: {e}")

    async def _wait_for_results(self):
        """
        Wait for the flight results to load.

        Modern websites load content dynamically, so we need to wait
        for the actual flight data to appear, not just the page to load.
        """
        try:
            # Wait for flight results to appear
            # These selectors target the flight result cards
            await self.page.wait_for_selector(
                '[data-test-id="searchResults"], '
                'div[class*="flight"], '
                'li[class*="pIav2d"], '  # Google's flight result class
                '[role="listitem"]',
                timeout=15000  # Wait up to 15 seconds
            )
            print("  ✓ Results loaded")

            # Extra wait for all results to fully render
            await self.page.wait_for_timeout(2000)

        except PlaywrightTimeout:
            print("  ⚠ Timeout waiting for results - page may still have content")

    async def _extract_flights(self) -> list[dict]:
        """
        Extract flight information from the search results.

        This is where we parse the actual flight data from the page.
        We look for specific elements that contain the information we need.

        Returns:
            List of dictionaries with flight details
        """
        flights = []

        try:
            # Save a screenshot for debugging (optional)
            await self.page.screenshot(path='debug_screenshot.png')
            print("  Screenshot saved to debug_screenshot.png")

            # Google Flights shows results in list items with specific structure
            # Each flight row contains: times, airline, duration, stops, price
            flight_data = await self.page.evaluate('''
                () => {
                    const flights = [];

                    // Find all flight result rows - they're in a list structure
                    // Look for elements that contain flight info patterns
                    const allLists = document.querySelectorAll('ul');

                    allLists.forEach(list => {
                        const items = list.querySelectorAll('li');

                        items.forEach(item => {
                            const text = item.textContent || '';

                            // A valid flight row should have:
                            // - A time pattern (e.g., "09:10" or "6:00")
                            // - A price pattern (e.g., "US$ 95" or "$95" or "R$ 500")
                            // - Duration pattern (e.g., "6h 28" or "6 h 28 min")

                            const hasTime = /\d{1,2}:\d{2}/.test(text);
                            const hasPrice = /(?:US\$|R\$|\$|€|£)\s*\d+/.test(text);
                            const hasDuration = /\d+\s*h\s*\d*\s*m?i?n?/.test(text);

                            // Must have at least time and price to be a flight row
                            if (hasTime && hasPrice && text.length < 500) {

                                // Extract times (format: 09:10 – 12:38 or 09:10 - 12:38)
                                const timePattern = /(\d{1,2}:\d{2})\s*[–\-−]\s*(\d{1,2}:\d{2})/;
                                const timeMatch = text.match(timePattern);
                                const departureTime = timeMatch ? timeMatch[1] : null;
                                const arrivalTime = timeMatch ? timeMatch[2] : null;

                                // Extract price (handles US$ 95, $95, R$ 500, €100, £80)
                                const pricePattern = /(?:US\$|R\$|\$|€|£)\s*([\d,\.]+)/;
                                const priceMatch = text.match(pricePattern);
                                const price = priceMatch ? priceMatch[0].trim() : null;

                                // Extract duration (6h 28 min, 6h 28m, 6 h 28 min)
                                const durationPattern = /(\d+)\s*h\s*(\d+)?\s*m?i?n?/i;
                                const durationMatch = text.match(durationPattern);
                                const duration = durationMatch ? durationMatch[0].trim() : null;

                                // Extract stops - handle multiple languages
                                let stops = "Unknown";
                                const textLower = text.toLowerCase();
                                if (textLower.includes("nonstop") ||
                                    textLower.includes("non-stop") ||
                                    textLower.includes("sem escalas") ||
                                    textLower.includes("direto")) {
                                    stops = "Nonstop";
                                } else {
                                    // Match "1 stop", "2 stops", "1 parada", "2 paradas", "1 escala"
                                    const stopMatch = text.match(/(\d+)\s*(?:stop|parada|escala)/i);
                                    if (stopMatch) {
                                        stops = stopMatch[1] + " stop(s)";
                                    }
                                }

                                // Extract airline - usually at the start or in specific spans
                                const airlineNames = [
                                    'Spirit', 'United', 'Delta', 'American', 'JetBlue',
                                    'Southwest', 'Frontier', 'Alaska', 'LATAM', 'Avianca',
                                    'Copa', 'Aeromexico', 'Air France', 'British Airways',
                                    'Lufthansa', 'Emirates', 'Qatar', 'TAP', 'Iberia', 'Azul', 'GOL'
                                ];
                                let airline = "Various";
                                for (const name of airlineNames) {
                                    if (text.includes(name)) {
                                        airline = name;
                                        break;
                                    }
                                }

                                // Only add if we have valid price (avoid duplicates)
                                if (price && !flights.some(f =>
                                    f.price === price &&
                                    f.departure_time === departureTime)) {
                                    flights.push({
                                        departure_time: departureTime,
                                        arrival_time: arrivalTime,
                                        duration: duration,
                                        stops: stops,
                                        airline: airline,
                                        price: price
                                    });
                                }
                            }
                        });
                    });

                    // Sort by price (extract number for comparison)
                    flights.sort((a, b) => {
                        const priceA = parseInt((a.price || '0').replace(/[^\d]/g, ''));
                        const priceB = parseInt((b.price || '0').replace(/[^\d]/g, ''));
                        return priceA - priceB;
                    });

                    // Return top 10 results
                    return flights.slice(0, 10);
                }
            ''')

            flights = flight_data if flight_data else []

            # If no flights found, try an alternative method
            if len(flights) == 0:
                print("  Trying alternative extraction method...")

                # Get page content and try regex extraction
                content = await self.page.content()

                flights.append({
                    'price': 'Could not extract - check debug_screenshot.png',
                    'departure_time': 'See screenshot',
                    'arrival_time': 'See screenshot',
                    'duration': 'See screenshot',
                    'stops': 'See screenshot',
                    'airline': 'See screenshot',
                    'note': 'Extraction failed - Google may have changed their page structure'
                })

        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
            flights.append({
                'error': str(e),
                'note': 'Try running with headless=False to debug'
            })

        return flights


# ============================================================================
# HELPER FUNCTION
# ============================================================================
async def search_google_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    headless: bool = True
) -> list[dict]:
    """
    Convenience function to search for flights without managing the scraper.

    This is what you'll typically call from other code.

    Example:
        flights = await search_google_flights(
            origin="New York",
            destination="Los Angeles",
            departure_date="2025-02-15"
        )
    """
    scraper = GoogleFlightsScraper(headless=headless)

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
        # Always close the browser, even if there's an error
        await scraper.close_browser()


# ============================================================================
# SAVE RESULTS TO FILE
# ============================================================================
def save_results_to_file(
    flights: list[dict],
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    filename: str = None
) -> str:
    """
    Save flight search results to a text file.

    FILE I/O CONCEPTS:
    - 'open()' opens a file for reading or writing
    - 'w' mode means "write" (creates new file or overwrites existing)
    - 'with' statement ensures the file is properly closed when done
    - 'f.write()' writes text to the file

    Args:
        flights: List of flight dictionaries from the search
        origin: Where the flight departs from
        destination: Where the flight goes to
        departure_date: Departure date (YYYY-MM-DD)
        return_date: Optional return date
        filename: Custom filename (optional, auto-generates if not provided)

    Returns:
        The path to the saved file
    """
    # Generate a filename if none provided
    # We include the route and date to make it easy to find later
    if filename is None:
        # Clean up city names for filename (remove spaces, special chars)
        origin_clean = origin.replace(" ", "_").replace(",", "")
        dest_clean = destination.replace(" ", "_").replace(",", "")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"flights_{origin_clean}_to_{dest_clean}_{timestamp}.txt"

    # Build the content string
    # We use a list and join() - more efficient than string concatenation
    lines = []

    # Header section
    lines.append("=" * 60)
    lines.append("FLIGHT SEARCH RESULTS")
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

    # Flight details
    if flights:
        for i, flight in enumerate(flights, 1):
            lines.append(f"FLIGHT {i}")
            lines.append("-" * 30)

            # Write each field nicely formatted
            for key, value in flight.items():
                # Capitalize the key and replace underscores with spaces
                nice_key = key.replace("_", " ").title()
                lines.append(f"  {nice_key}: {value}")

            lines.append("")  # Blank line between flights
    else:
        lines.append("No flights found.")
        lines.append("")

    # Footer
    lines.append("=" * 60)
    lines.append("End of results")
    lines.append("=" * 60)

    # Join all lines with newline character
    content = "\n".join(lines)

    # Write to file
    # 'with' is a context manager - it automatically closes the file
    # even if an error occurs
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✓ Results saved to: {filename}")
    return filename


# ============================================================================
# TEST CODE
# ============================================================================
# This block only runs when you execute this file directly
# (not when importing it as a module)
if __name__ == "__main__":

    async def test_scraper():
        """
        Test the scraper with a sample search.

        We search for flights from New York to Los Angeles,
        departing 2 weeks from today.
        """
        print("=" * 60)
        print("GOOGLE FLIGHTS SCRAPER TEST")
        print("=" * 60)

        # Calculate dates (2 weeks from now)
        today = datetime.now()
        departure = today + timedelta(days=14)
        return_date = today + timedelta(days=21)  # 3 weeks from now

        # Format dates as YYYY-MM-DD (this is ISO format, widely used in programming)
        departure_str = departure.strftime('%Y-%m-%d')
        return_str = return_date.strftime('%Y-%m-%d')

        print(f"\nTest search:")
        print(f"  From: New York (JFK)")
        print(f"  To: Los Angeles (LAX)")
        print(f"  Departure: {departure_str}")
        print(f"  Return: {return_str}")
        print()

        # Run the search
        # Set headless=False to watch the browser in action!
        flights = await search_google_flights(
            origin="New York",
            destination="Los Angeles",
            departure_date=departure_str,
            return_date=return_str,
            headless=False  # Set to True for invisible browser
        )

        # Display results
        print("\n" + "=" * 60)
        print("SEARCH RESULTS")
        print("=" * 60)

        if flights:
            for i, flight in enumerate(flights, 1):
                print(f"\nFlight {i}:")
                for key, value in flight.items():
                    print(f"  {key}: {value}")

            # Save results to a text file
            saved_file = save_results_to_file(
                flights=flights,
                origin="New York",
                destination="Los Angeles",
                departure_date=departure_str,
                return_date=return_str
            )
            print(f"\nResults have been saved! You can open '{saved_file}' to see them.")
        else:
            print("\nNo flights found. This could mean:")
            print("  - Google Flights changed their page structure")
            print("  - There was a network issue")
            print("  - The search didn't complete properly")
            print("\nTry running with headless=False to see what's happening!")

        return flights

    # Run the test
    # asyncio.run() is how we execute async functions from regular Python
    asyncio.run(test_scraper())
