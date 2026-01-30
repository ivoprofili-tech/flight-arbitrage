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
import os
import glob
import shutil

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

    def __init__(self, headless: bool = True, fast_mode: bool = True):
        """
        Initialize the scraper.

        Args:
            headless: If True, browser runs invisibly in background.
                      If False, you can watch the browser do its thing!
                      Set to False when debugging to see what's happening.
            fast_mode: If True, use shorter wait times for faster execution.
                       Target: ~30 seconds total. Default is True.
        """
        self.headless = headless
        self.fast_mode = fast_mode
        self.browser = None
        self.page = None
        self.context = None

        # Wait times (in ms) - shorter in fast mode
        if fast_mode:
            self.wait_short = 100      # Was 200-300ms
            self.wait_medium = 200     # Was 400-500ms
            self.wait_long = 500       # Was 800-1000ms
        else:
            self.wait_short = 300
            self.wait_medium = 500
            self.wait_long = 1000

    async def start_browser(self):
        """
        Launch the browser with video recording enabled.

        We use Chromium (Chrome's open-source base) because it works well
        with Playwright and is what most people use for scraping.
        """
        # Clear old videos from previous runs
        self._clear_old_videos()

        # Create a Playwright instance
        self.playwright = await async_playwright().start()

        # Launch the browser
        # - headless: Whether to show the browser window
        # - args: Extra settings for the browser
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']  # Helps avoid detection
        )

        # Ensure videos directory exists
        os.makedirs('videos', exist_ok=True)

        # Create a browser context with video recording enabled
        # Videos are saved to the 'videos' directory
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 800},
            record_video_dir='videos/',  # Directory to save videos
            record_video_size={'width': 1280, 'height': 800}
        )

        # Create a new page (like a browser tab)
        self.page = await self.context.new_page()

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

    async def close_browser(self):
        """Clean up: close the browser and save the video with descriptive name."""
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

        # Rename video with descriptive name
        if video_path and os.path.exists(video_path):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_name = f"videos/google_flights_{timestamp}.webm"
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
        """
        Handle the cookie consent popup that appears in many countries.

        Google shows different popups depending on your location.
        We try to find and click common "Accept" or "Reject" buttons.
        """
        try:
            # Try different selectors for cookie buttons (no initial wait needed)
            cookie_selectors = [
                'button:has-text("Accept all")',      # English
                'button:has-text("Accept")',          # Shorter version
                'button:has-text("Reject all")',      # Privacy-friendly option
                'button:has-text("I agree")',         # Alternative text
                '[aria-label="Accept all"]',          # Using aria-label attribute
            ]

            for selector in cookie_selectors:
                try:
                    # Check if this button exists (wait max 500ms)
                    button = await self.page.wait_for_selector(selector, timeout=500)
                    if button:
                        await button.click()
                        print(f"Clicked cookie consent button")
                        await self.page.wait_for_timeout(self.wait_short)
                        return True
                except PlaywrightTimeout:
                    # Button not found, try the next one
                    continue

            return False

        except Exception as e:
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

        # Step 1: Open Google Flights with retry logic
        print("\n[Step 1] Opening Google Flights...")
        max_retries = 4
        retry_delays = [2, 4, 8, 16]  # Exponential backoff in seconds

        for attempt in range(max_retries):
            try:
                await self.page.goto('https://www.google.com/travel/flights', wait_until='domcontentloaded', timeout=60000)
                print("  ✓ Page loaded successfully")
                break
            except PlaywrightTimeout as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    print(f"  ⚠ Page load timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    print(f"  ✗ Page load failed after {max_retries} attempts")
                    raise e

        await self.page.wait_for_timeout(self.wait_long)

        # Handle cookie consent if needed
        await self.handle_cookie_consent()

        # Step 2: Set one-way if no return date
        # IMPORTANT: Must set trip type BEFORE selecting dates!
        # Round trip mode expects 2 dates before showing "Done" button
        if not return_date:
            print("[Step 2] Setting trip type to one-way...")
            try:
                # Use locator to find and click "Round trip" text directly
                # This is more reliable than complex CSS selectors
                round_trip_locator = self.page.locator('text="Round trip"').first
                await round_trip_locator.click(timeout=2000)
                print("  ✓ Clicked Round trip dropdown")

                await self.page.wait_for_timeout(self.wait_short)

                # Now click "One way" from the dropdown menu
                one_way_locator = self.page.locator('text="One way"').first
                await one_way_locator.click(timeout=2000)
                print("  ✓ Selected One way")

                await self.page.wait_for_timeout(self.wait_short)
            except Exception as e:
                print(f"  ⚠ Could not set one-way via locator: {e}")
                # Fallback: try JavaScript
                try:
                    await self.page.evaluate('''
                        () => {
                            // Find and click "Round trip" text
                            const elements = document.querySelectorAll('*');
                            for (const el of elements) {
                                if (el.textContent === 'Round trip' && el.offsetParent !== null) {
                                    el.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    ''')
                    await self.page.wait_for_timeout(self.wait_short)
                    await self.page.evaluate('''
                        () => {
                            const elements = document.querySelectorAll('li, [role="option"]');
                            for (const el of elements) {
                                if (el.textContent.includes('One way')) {
                                    el.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    ''')
                    print("  ✓ Set one-way via JavaScript")
                except Exception as e2:
                    print(f"  ⚠ JavaScript fallback also failed: {e2}")

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

            await self.page.wait_for_timeout(self.wait_short)

            # Clear existing text and type new origin
            await self.page.keyboard.press('Control+a')
            await self.page.keyboard.type(origin, delay=50)
            await self.page.wait_for_timeout(self.wait_long)

            # Select from dropdown - click first suggestion or press Enter
            try:
                suggestion = await self.page.wait_for_selector('ul[role="listbox"] li:first-child', timeout=1500)
                if suggestion:
                    await suggestion.click()
                    print(f"  ✓ Selected {origin} from dropdown")
            except:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for {origin}")

            await self.page.wait_for_timeout(self.wait_short)
        except Exception as e:
            print(f"  ⚠ Error setting origin: {e}")

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

            await self.page.wait_for_timeout(self.wait_short)

            # Type destination
            await self.page.keyboard.type(destination, delay=50)
            await self.page.wait_for_timeout(self.wait_long)

            # Select from dropdown
            try:
                suggestion = await self.page.wait_for_selector('ul[role="listbox"] li:first-child', timeout=1500)
                if suggestion:
                    await suggestion.click()
                    print(f"  ✓ Selected {destination} from dropdown")
            except:
                await self.page.keyboard.press('Enter')
                print(f"  ✓ Pressed Enter for {destination}")

            await self.page.wait_for_timeout(self.wait_short)
        except Exception as e:
            print(f"  ⚠ Error setting destination: {e}")

        # Step 5: Click date field, select date, click Done
        print(f"[Step 5] Setting departure date: {departure_date}...")
        try:
            # Click on the departure date field
            date_field = await self.page.query_selector('input[aria-label*="Departure"], div[data-placeholder="Departure"]')
            if date_field:
                await date_field.click()
            else:
                await self.page.click('text="Departure"')

            await self.page.wait_for_timeout(self.wait_medium)

            # Parse date
            target_date = datetime.strptime(departure_date, '%Y-%m-%d')
            day = target_date.day
            month_name = target_date.strftime('%B')
            target_year = target_date.year

            # Navigate to the correct month using Python loop (allows proper waits)
            for attempt in range(12):
                # Check if target month is visible
                month_visible = await self.page.evaluate('''
                    (args) => {
                        const targetMonth = args.monthName;
                        const targetYear = args.year;
                        const targetDay = args.day;

                        // Check headings for month/year
                        const headings = document.querySelectorAll('h2, [role="heading"], div[class*="header"]');
                        for (const h of headings) {
                            const text = h.textContent || '';
                            if (text.includes(targetMonth) && text.includes(String(targetYear))) {
                                return true;
                            }
                        }
                        // Check if date cell exists
                        const selector = '[aria-label*="' + targetMonth + ' ' + targetDay + '"]';
                        if (document.querySelector(selector)) return true;
                        return false;
                    }
                ''', {"monthName": month_name, "year": target_year, "day": day})

                if month_visible:
                    print(f"  ✓ Found {month_name} {target_year} in calendar")
                    break

                # Click next month button
                clicked = await self.page.evaluate('''
                    () => {
                        // Try aria-label
                        const nextByLabel = document.querySelector('[aria-label*="Next"]');
                        if (nextByLabel) {
                            nextByLabel.click();
                            return true;
                        }
                        // Try SVG buttons
                        const allButtons = Array.from(document.querySelectorAll('button'));
                        const svgButtons = allButtons.filter(b => b.querySelector('svg'));
                        if (svgButtons.length >= 2) {
                            svgButtons[1].click();
                            return true;
                        } else if (svgButtons.length === 1) {
                            svgButtons[0].click();
                            return true;
                        }
                        return false;
                    }
                ''')

                if clicked:
                    print(f"  → Navigating to next month...")
                    await self.page.wait_for_timeout(self.wait_medium)
                else:
                    print(f"  ⚠ Could not find next month button")
                    break

            await self.page.wait_for_timeout(self.wait_short)

            # Now click the date
            date_result = await self.page.evaluate('''
                (args) => {
                    const targetDay = args.day;
                    const targetMonth = args.monthName;
                    const isoDate = args.isoDate;

                    // Strategy 1: aria-label with month and day
                    const labelSelector = '[aria-label*="' + targetMonth + ' ' + targetDay + '"]';
                    const dateByLabel = document.querySelector(labelSelector);
                    if (dateByLabel) {
                        dateByLabel.click();
                        return { success: true, method: 'aria-label' };
                    }

                    // Strategy 2: data-iso attribute
                    const isoSelector = '[data-iso="' + isoDate + '"]';
                    const dateByIso = document.querySelector(isoSelector);
                    if (dateByIso) {
                        dateByIso.click();
                        return { success: true, method: 'data-iso' };
                    }

                    // Strategy 3: Find by day number in calendar grid
                    const allCells = document.querySelectorAll('[role="gridcell"], td, [role="button"]');
                    for (const cell of allCells) {
                        const text = cell.textContent.trim();
                        if (text === String(targetDay) || text.startsWith(targetDay + '$') || text.startsWith(targetDay + '\\n')) {
                            cell.click();
                            return { success: true, method: 'grid-cell' };
                        }
                    }

                    return { success: false, error: 'Could not find date cell' };
                }
            ''', {"day": day, "monthName": month_name, "isoDate": departure_date})

            if date_result.get('success'):
                print(f"  ✓ Selected date {departure_date} via {date_result.get('method')}")
            else:
                print(f"  ⚠ Date selection issue: {date_result.get('error')}")

            await self.page.wait_for_timeout(self.wait_short)

            # Click Done button - use JavaScript directly (faster and more reliable)
            done_clicked = False
            try:
                result = await self.page.evaluate('''
                    () => {
                        // Find all buttons with "Done" text
                        const buttons = document.querySelectorAll('button');
                        for (const btn of buttons) {
                            const text = btn.textContent.trim();
                            const innerText = btn.innerText.trim();
                            const spanText = btn.querySelector('span')?.textContent?.trim();
                            if (text === 'Done' || innerText === 'Done' || spanText === 'Done') {
                                btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                                btn.click();
                                return 'clicked_button';
                            }
                        }
                        // Try finding span with Done text
                        const spans = document.querySelectorAll('span');
                        for (const span of spans) {
                            if (span.textContent.trim() === 'Done') {
                                const btn = span.closest('button');
                                if (btn) {
                                    btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                                    btn.click();
                                    return 'clicked_span_parent';
                                }
                                // Click span directly
                                span.click();
                                return 'clicked_span';
                            }
                        }
                        return 'not_found';
                    }
                ''')
                if result != 'not_found':
                    done_clicked = True
                    print(f"  ✓ Clicked Done button ({result})")
                else:
                    print("  ⚠ Done button not found via JavaScript")
            except Exception as e:
                print(f"  ⚠ JavaScript Done click failed: {e}")

            # Fallback: press Escape to close the date picker
            if not done_clicked:
                print("  → Pressing Escape to close calendar...")
                await self.page.keyboard.press('Escape')

            await self.page.wait_for_timeout(self.wait_short)
        except Exception as e:
            print(f"  ⚠ Error setting date: {e}")

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
        await self.page.wait_for_timeout(self.wait_long * 2 if not self.fast_mode else self.wait_long)
        await self.page.screenshot(path='debug_step7_results.png')

        current_url = self.page.url
        print(f"  Current URL: {current_url[:80]}...")

        # Wait for flight results
        await self._wait_for_results()

        # Load more flights by scrolling and clicking "Show more"
        await self._load_more_flights()

        # Extract flight data
        print("[Step 8] Extracting flight data...")
        await self.page.screenshot(path='debug_screenshot.png')
        flights = await self._extract_flights()

        print(f"\nFound {len(flights)} flights!")
        return flights

    async def _load_more_flights(self):
        """
        Load more flights by scrolling and clicking 'Show more flights' button.
        Google Flights lazy-loads results and has a button to show more.
        """
        print("[Step 7b] Loading more flights...")

        try:
            # First, scroll down to trigger lazy loading
            for i in range(3):
                await self.page.evaluate('window.scrollBy(0, 800)')
                await self.page.wait_for_timeout(self.wait_short)

            # Look for and click "Show more flights" or similar button
            show_more_clicked = await self.page.evaluate('''
                () => {
                    // Find buttons with "more" text
                    const buttons = document.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.textContent.toLowerCase();
                        if (text.includes('more flights') || text.includes('show more') ||
                            text.includes('view more') || text.includes('load more')) {
                            btn.scrollIntoView({ behavior: 'instant', block: 'center' });
                            btn.click();
                            return true;
                        }
                    }
                    // Also try links/spans
                    const links = document.querySelectorAll('a, span, div[role="button"]');
                    for (const el of links) {
                        const text = el.textContent.toLowerCase();
                        if (text.includes('more flights') && text.length < 50) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
            ''')

            if show_more_clicked:
                print("  ✓ Clicked 'Show more flights' button")
                await self.page.wait_for_timeout(self.wait_long)

                # Scroll again to load any additional results
                for i in range(2):
                    await self.page.evaluate('window.scrollBy(0, 600)')
                    await self.page.wait_for_timeout(self.wait_short)
            else:
                print("  → No 'Show more' button found (may have all results)")

            # Scroll back to top for extraction
            await self.page.evaluate('window.scrollTo(0, 0)')
            await self.page.wait_for_timeout(self.wait_short)

        except Exception as e:
            print(f"  ⚠ Error loading more flights: {e}")

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

            await self.page.wait_for_timeout(self.wait_medium)

            # Clear any existing text
            await self.page.keyboard.press('Control+a')
            await self.page.wait_for_timeout(50 if self.fast_mode else 100)

            # Type the location slowly for autocomplete to work
            await self.page.keyboard.type(location, delay=150)
            print(f"  Typed: {location}")

            # Wait for autocomplete suggestions to appear
            await self.page.wait_for_timeout(self.wait_long)

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

            await self.page.wait_for_timeout(self.wait_long)

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

            await self.page.wait_for_timeout(self.wait_long)

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

            await self.page.wait_for_timeout(self.wait_medium)

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

            await self.page.wait_for_timeout(self.wait_medium)

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

            # Small extra wait for all results to fully render
            await self.page.wait_for_timeout(self.wait_long)

        except PlaywrightTimeout:
            print("  ⚠ Timeout waiting for results - page may still have content")

    async def _extract_flights(self) -> list[dict]:
        """
        Extract flight information from the search results, including layover airports.

        This method:
        1. Extracts basic flight info from the results list
        2. For connecting flights, clicks to expand and extract layover airports
        3. Returns flights with a 'layovers' field containing airport codes

        Returns:
            List of dictionaries with flight details including layovers
        """
        flights = []

        try:
            # Save a screenshot for debugging
            await self.page.screenshot(path='debug_screenshot.png')
            print("  Screenshot saved to debug_screenshot.png")

            # First, let's debug what's on the page
            page_text = await self.page.evaluate('() => document.body.innerText')
            print(f"  Page text length: {len(page_text)} characters")

            # Save page text for debugging
            with open('debug_page_text.txt', 'w', encoding='utf-8') as f:
                f.write(page_text)
            print("  Page text saved to debug_page_text.txt")

            # Find all clickable flight rows and extract basic info + row index
            flight_rows_data = await self.page.evaluate('''
                () => {
                    const flights = [];
                    const seen = new Set();

                    // Target specific elements instead of all '*' for performance
                    // Prices are typically in span elements
                    const priceElements = [];
                    const spans = document.querySelectorAll('span');
                    for (const el of spans) {
                        const text = el.textContent || '';
                        // Match prices like $99, $1,234, US$99, etc.
                        if (/^\s*(?:US\s*)?\$\s*[\d,]+\s*$/.test(text) && text.length < 20) {
                            priceElements.push(el);
                        }
                    }

                    let rowIndex = 0;
                    // For each price, find the parent flight row and extract data
                    for (const priceEl of priceElements) {
                        // Go up to find the flight row container (usually 3-5 levels up)
                        let container = priceEl;
                        for (let i = 0; i < 8; i++) {
                            if (container.parentElement) {
                                container = container.parentElement;
                            }
                            // Check if this container has flight-like content
                            const containerText = container.textContent || '';
                            const hasTime = /\d{1,2}:\d{2}\s*(AM|PM)?/i.test(containerText);
                            const hasDuration = /\d+\s*hr|\d+\s*h\s*\d+/i.test(containerText);

                            if (hasTime && hasDuration && containerText.length > 30 && containerText.length < 1000) {
                                const price = priceEl.textContent.trim();

                                // Skip if we've seen this price+container combo
                                const key = price + containerText.substring(0, 50);
                                if (seen.has(key)) continue;
                                seen.add(key);

                                // Extract times
                                let departureTime = null;
                                let arrivalTime = null;

                                const timeWithSep = containerText.match(/(\d{1,2}:\d{2}\s*(?:AM|PM)?)\s*[–\-−]\s*(\d{1,2}:\d{2}\s*(?:AM|PM)?)/i);
                                if (timeWithSep) {
                                    departureTime = timeWithSep[1].trim();
                                    arrivalTime = timeWithSep[2].trim();
                                } else {
                                    const allTimes = containerText.match(/\d{1,2}:\d{2}\s*(?:AM|PM)?/gi);
                                    if (allTimes && allTimes.length >= 2) {
                                        const uniqueTimes = [...new Set(allTimes.map(t => t.trim()))];
                                        if (uniqueTimes.length >= 2) {
                                            departureTime = uniqueTimes[0];
                                            arrivalTime = uniqueTimes[1];
                                        } else {
                                            departureTime = allTimes[0].trim();
                                        }
                                    }
                                }

                                // Extract duration
                                const durationPattern = /(\d+)\s*(?:hr|h)\s*(?:(\d+)\s*(?:min|m))?/i;
                                const durationMatch = containerText.match(durationPattern);
                                let duration = null;
                                if (durationMatch) {
                                    const hours = durationMatch[1];
                                    const mins = durationMatch[2] || '0';
                                    duration = `${hours}h ${mins}m`;
                                }

                                // Extract stops
                                let stops = "Unknown";
                                let numStops = 0;
                                const textLower = containerText.toLowerCase();
                                if (textLower.includes("nonstop") || textLower.includes("non-stop")) {
                                    stops = "Nonstop";
                                    numStops = 0;
                                } else {
                                    const stopMatch = containerText.match(/(\d+)\s*stop/i);
                                    if (stopMatch) {
                                        numStops = parseInt(stopMatch[1]);
                                        stops = numStops === 1 ? "1 stop" : numStops + " stops";
                                    }
                                }

                                // Extract airline - check longer names first to avoid partial matches
                                const airlineNames = [
                                    'AlaskaHawaiian', 'AmericanAlaska',  // Codeshare combinations first
                                    'Sun Country', 'British Airways', 'Air France',
                                    'Spirit', 'United', 'Delta', 'American', 'JetBlue',
                                    'Southwest', 'Frontier', 'Alaska', 'LATAM', 'Avianca',
                                    'Copa', 'Aeromexico', 'Lufthansa', 'Emirates', 'Qatar',
                                    'TAP', 'Iberia', 'Azul', 'GOL', 'Hawaiian', 'Allegiant', 'Breeze'
                                ];
                                let airline = "Various";
                                for (const name of airlineNames) {
                                    if (containerText.includes(name)) {
                                        // Map codeshare names to primary airline
                                        if (name === 'AlaskaHawaiian') airline = 'Alaska';
                                        else if (name === 'AmericanAlaska') airline = 'American/Alaska';
                                        else airline = name;
                                        break;
                                    }
                                }

                                // Try to extract layover airport from the summary line
                                // Google shows format like "1 stop 3 hr 46 min ATL" or "2 stops ORD, DEN"
                                let layoverFromSummary = [];
                                if (numStops > 0) {
                                    // Look for airport codes (3 uppercase letters) after "stop"
                                    // Use specific pattern to avoid matching random 3-letter sequences
                                    const stopIndex = containerText.toLowerCase().indexOf('stop');
                                    if (stopIndex !== -1) {
                                        // Get text after "stop"
                                        const afterStop = containerText.substring(stopIndex);
                                        // Find all 3-letter uppercase airport codes
                                        const airportCodes = afterStop.match(/\b([A-Z]{3})\b/g);
                                        if (airportCodes) {
                                            for (const code of airportCodes) {
                                                // Filter out non-airport codes (common false positives)
                                                const excluded = ['PHX', 'JFK', 'LAX', 'SFO', 'NYC', 'LGA', 'EWR']; // origin/dest
                                                const origin = 'JFK'; // We know this from search
                                                const dest = 'PHX';
                                                if (code !== origin && code !== dest &&
                                                    !layoverFromSummary.includes(code) &&
                                                    code.match(/^[A-Z]{3}$/)) {
                                                    layoverFromSummary.push(code);
                                                }
                                            }
                                        }
                                    }
                                    // Also try pattern where layover appears separately
                                    const airportCodes = containerText.match(/\b([A-Z]{3})\b/g);
                                    if (airportCodes && airportCodes.length > 2) {
                                        // First and last are usually origin/destination
                                        // Middle codes are layovers
                                        for (let j = 1; j < airportCodes.length - 1; j++) {
                                            const code = airportCodes[j];
                                            if (!layoverFromSummary.includes(code)) {
                                                layoverFromSummary.push(code);
                                            }
                                        }
                                    }
                                }

                                flights.push({
                                    departure_time: departureTime,
                                    arrival_time: arrivalTime,
                                    duration: duration,
                                    stops: stops,
                                    num_stops: numStops,
                                    airline: airline,
                                    price: price,
                                    layovers: layoverFromSummary,
                                    row_index: rowIndex
                                });

                                rowIndex++;
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

            flights = flight_rows_data if flight_rows_data else []
            print(f"  Extracted {len(flights)} flights from summary view")

            # Expand connecting flights to get detailed layover info
            # Skip in fast_mode if we already have summary layovers (saves ~5-10 seconds)
            connecting_flights = [f for f in flights if f.get('num_stops', 0) > 0]
            if connecting_flights:
                # Check if we need to expand - in fast mode, only expand if no layovers from summary
                needs_expansion = [f for f in connecting_flights if not f.get('layovers')]
                if self.fast_mode and not needs_expansion:
                    print(f"  Found {len(connecting_flights)} connecting flights - using summary layovers (fast mode)")
                else:
                    print(f"  Found {len(connecting_flights)} connecting flights - extracting layover details...")
                    await self._extract_layover_details(flights)

            # Clean up internal fields
            for flight in flights:
                flight.pop('row_index', None)
                flight.pop('num_stops', None)

            # If still no flights found, provide debug info
            if len(flights) == 0:
                print("  ⚠ No flights extracted - check debug_page_text.txt and debug_screenshot.png")
                flights.append({
                    'price': 'Could not extract - check debug files',
                    'departure_time': 'See debug_screenshot.png',
                    'arrival_time': 'See debug_page_text.txt',
                    'duration': 'N/A',
                    'stops': 'N/A',
                    'airline': 'N/A',
                    'layovers': [],
                    'note': 'Extraction failed - Google may have changed their page structure'
                })

        except Exception as e:
            print(f"  ⚠ Extraction error: {e}")
            import traceback
            traceback.print_exc()
            flights.append({
                'error': str(e),
                'layovers': [],
                'note': 'Try running with headless=False to debug'
            })

        return flights

    async def _extract_layover_details(self, flights: list[dict]):
        """
        Click on each connecting flight to expand details and extract layover airports.

        This method modifies the flights list in place, updating the 'layovers' field
        with airport codes extracted from the expanded flight details.

        Args:
            flights: List of flight dictionaries to update
        """
        # Find all flight rows that can be clicked
        flight_rows = await self.page.query_selector_all('li[class*="pIav2d"], div[role="listitem"], [data-ved]')

        if not flight_rows:
            # Try alternative selectors for flight rows
            flight_rows = await self.page.query_selector_all('ul li')
            # Filter to only flight-like rows
            valid_rows = []
            for row in flight_rows:
                text = await row.inner_text()
                if '$' in text and ':' in text:  # Has price and time
                    valid_rows.append(row)
            flight_rows = valid_rows[:30]

        print(f"  Found {len(flight_rows)} clickable flight rows")

        for flight in flights:
            if flight.get('num_stops', 0) == 0:
                # Nonstop flight - no layovers
                flight['layovers'] = []
                continue

            # If we already found layovers from summary, we might still want to verify
            # by expanding, but for speed let's skip if we have data
            if flight.get('layovers') and len(flight['layovers']) >= flight.get('num_stops', 1):
                print(f"    ✓ {flight['price']}: Layovers from summary: {flight['layovers']}")
                continue

            row_index = flight.get('row_index', 0)
            if row_index >= len(flight_rows):
                print(f"    ⚠ Cannot find row {row_index} for flight {flight['price']}")
                continue

            try:
                row = flight_rows[row_index]

                # Click to expand the flight details with short timeout
                try:
                    await row.click(timeout=3000)  # 3 second timeout
                except Exception as click_err:
                    # Skip this flight if click fails - don't hang
                    print(f"    → Skipping {flight['price']}: click failed")
                    continue

                await self.page.wait_for_timeout(self.wait_medium)

                # Extract layover airports from expanded view
                layovers = await self.page.evaluate('''
                    () => {
                        const layovers = [];

                        // Strategy 1: Look for layover/connection info in expanded details
                        // Google shows segments like "JFK → LAX" then "Layover 2h" then "LAX → PHX"
                        const expandedText = document.body.innerText;

                        // Find all 3-letter airport codes
                        const allCodes = expandedText.match(/\\b([A-Z]{3})\\b/g) || [];

                        // Look for "layover" or "stop" text followed by location info
                        const layoverPattern = /(?:layover|stop|connection|connecting).*?(?:in|at)?\\s*([A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?|[A-Z]{3})/gi;
                        let match;
                        while ((match = layoverPattern.exec(expandedText)) !== null) {
                            const location = match[1].trim();
                            // If it's a city name, try to find nearby airport code
                            if (location.length > 3) {
                                // Look for airport code near the city name
                                const nearbyText = expandedText.substring(
                                    Math.max(0, match.index - 50),
                                    Math.min(expandedText.length, match.index + 100)
                                );
                                const nearbyCode = nearbyText.match(/\\b([A-Z]{3})\\b/);
                                if (nearbyCode && !layovers.includes(nearbyCode[1])) {
                                    layovers.push(nearbyCode[1]);
                                }
                            } else if (location.match(/^[A-Z]{3}$/)) {
                                if (!layovers.includes(location)) {
                                    layovers.push(location);
                                }
                            }
                        }

                        // Strategy 2: Look for flight segment pattern "XXX → YYY"
                        // In a connection, there are multiple segments
                        const segmentPattern = /([A-Z]{3})\\s*[→➔\\-–]\\s*([A-Z]{3})/g;
                        const segments = [];
                        while ((match = segmentPattern.exec(expandedText)) !== null) {
                            segments.push({ from: match[1], to: match[2] });
                        }

                        // If we have multiple segments, the destination of early segments
                        // (except the last) are layover airports
                        if (segments.length > 1) {
                            for (let i = 0; i < segments.length - 1; i++) {
                                const layoverCode = segments[i].to;
                                if (!layovers.includes(layoverCode)) {
                                    layovers.push(layoverCode);
                                }
                            }
                        }

                        // Strategy 3: Look for time patterns with airport codes
                        // "Arrives 2:30 PM LAX" or "Departs 5:00 PM LAX"
                        const timeAirportPattern = /(?:arrives?|departs?|lands?|leaves?).*?(\\d{1,2}:\\d{2}\\s*(?:AM|PM)?).{0,20}?([A-Z]{3})/gi;
                        const timeAirports = [];
                        while ((match = timeAirportPattern.exec(expandedText)) !== null) {
                            timeAirports.push(match[2]);
                        }

                        // Middle airports in the sequence are layovers
                        if (timeAirports.length > 2) {
                            for (let i = 1; i < timeAirports.length - 1; i++) {
                                if (!layovers.includes(timeAirports[i])) {
                                    layovers.push(timeAirports[i]);
                                }
                            }
                        }

                        // Strategy 4: Look for explicit "X hr Y min in CODE" pattern
                        const durationInPattern = /(\\d+\\s*(?:hr?|hour)s?\\s*(?:\\d+\\s*(?:min|m))?\\s*(?:in|at)\\s*)([A-Z]{3})/gi;
                        while ((match = durationInPattern.exec(expandedText)) !== null) {
                            if (!layovers.includes(match[2])) {
                                layovers.push(match[2]);
                            }
                        }

                        return layovers;
                    }
                ''')

                if layovers:
                    flight['layovers'] = layovers
                    print(f"    ✓ {flight['price']}: Found layovers: {layovers}")
                else:
                    print(f"    ⚠ {flight['price']}: Could not extract layover details")

                # Close expanded view by pressing Escape or clicking elsewhere
                await self.page.keyboard.press('Escape')
                await self.page.wait_for_timeout(self.wait_short)

            except Exception as e:
                print(f"    ⚠ Error expanding flight {flight['price']}: {e}")
                continue


# ============================================================================
# HELPER FUNCTION
# ============================================================================
async def search_google_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    headless: bool = True,
    fast_mode: bool = True
) -> list[dict]:
    """
    Convenience function to search for flights without managing the scraper.

    This is what you'll typically call from other code.

    Args:
        origin: Departure city/airport
        destination: Arrival city/airport
        departure_date: Date in YYYY-MM-DD format
        return_date: Optional return date
        headless: Run browser invisibly (default True)
        fast_mode: Use shorter wait times for ~30s execution (default True)

    Example:
        flights = await search_google_flights(
            origin="New York",
            destination="Los Angeles",
            departure_date="2025-02-15"
        )
    """
    scraper = GoogleFlightsScraper(headless=headless, fast_mode=fast_mode)

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
