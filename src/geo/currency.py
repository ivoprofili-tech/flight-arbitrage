"""
Currency Conversion Module

Auto-fetches exchange rates and normalizes prices to USD for comparison.
Uses free exchange rate APIs with fallback to static rates.

APIs used (in order of preference):
1. ExchangeRate-API (free tier: 1500 requests/month)
2. Open Exchange Rates (free tier with USD base)
3. Static fallback rates
"""

import asyncio
import aiohttp
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExchangeRates:
    """Exchange rates with metadata."""
    rates: Dict[str, float]  # Currency code -> rate to USD
    timestamp: datetime
    source: str

    def get_rate(self, currency: str) -> Optional[float]:
        """Get the rate for a currency to USD."""
        return self.rates.get(currency.upper())

    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if rates are older than max_age_hours."""
        age = datetime.now() - self.timestamp
        return age > timedelta(hours=max_age_hours)


# Static fallback rates (updated periodically)
# These are approximate rates for when APIs are unavailable
STATIC_RATES = {
    "USD": 1.0,
    "BRL": 0.20,    # 1 BRL ≈ 0.20 USD (5 BRL = 1 USD)
    "COP": 0.00025, # 1 COP ≈ 0.00025 USD (4000 COP = 1 USD)
    "ARS": 0.0011,  # 1 ARS ≈ 0.0011 USD (900 ARS = 1 USD)
    "EUR": 1.08,    # 1 EUR ≈ 1.08 USD
    "GBP": 1.27,    # 1 GBP ≈ 1.27 USD
    "MXN": 0.058,   # 1 MXN ≈ 0.058 USD
    "CLP": 0.0011,  # 1 CLP ≈ 0.0011 USD
    "PEN": 0.27,    # 1 PEN ≈ 0.27 USD
}


class CurrencyConverter:
    """
    Currency converter with auto-fetch and caching.

    Usage:
        converter = CurrencyConverter()
        await converter.update_rates()  # Fetch latest rates

        usd_price = converter.convert(5000, "BRL")  # Convert 5000 BRL to USD
    """

    def __init__(self, cache_hours: int = 24):
        """
        Initialize the converter.

        Args:
            cache_hours: How long to cache exchange rates
        """
        self.cache_hours = cache_hours
        self._rates: Optional[ExchangeRates] = None
        self._lock = asyncio.Lock()

    @property
    def rates(self) -> Dict[str, float]:
        """Get current rates dict."""
        if self._rates:
            return self._rates.rates
        return STATIC_RATES

    async def update_rates(self, force: bool = False) -> bool:
        """
        Fetch latest exchange rates from APIs.

        Args:
            force: Force update even if cache is fresh

        Returns:
            True if rates were updated, False if using cached/static
        """
        async with self._lock:
            # Check if we need to update
            if not force and self._rates and not self._rates.is_stale(self.cache_hours):
                logger.debug("Using cached exchange rates")
                return False

            # Try APIs in order
            rates = await self._fetch_from_exchangerate_api()
            if rates:
                self._rates = rates
                logger.info(f"Updated exchange rates from {rates.source}")
                return True

            rates = await self._fetch_from_frankfurter()
            if rates:
                self._rates = rates
                logger.info(f"Updated exchange rates from {rates.source}")
                return True

            # Fall back to static rates
            logger.warning("Using static fallback exchange rates")
            self._rates = ExchangeRates(
                rates=STATIC_RATES.copy(),
                timestamp=datetime.now(),
                source="static_fallback"
            )
            return False

    async def _fetch_from_exchangerate_api(self) -> Optional[ExchangeRates]:
        """Fetch from ExchangeRate-API (free, no key required for basic)."""
        try:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Convert rates to USD base (invert since API gives USD->X)
                        rates = {}
                        for currency, rate in data.get("rates", {}).items():
                            if rate > 0:
                                rates[currency] = 1.0 / rate  # X->USD
                        rates["USD"] = 1.0

                        return ExchangeRates(
                            rates=rates,
                            timestamp=datetime.now(),
                            source="exchangerate-api.com"
                        )
        except Exception as e:
            logger.debug(f"ExchangeRate-API failed: {e}")
        return None

    async def _fetch_from_frankfurter(self) -> Optional[ExchangeRates]:
        """Fetch from Frankfurter API (free, open source)."""
        try:
            url = "https://api.frankfurter.app/latest?from=USD"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rates = {}
                        for currency, rate in data.get("rates", {}).items():
                            if rate > 0:
                                rates[currency] = 1.0 / rate
                        rates["USD"] = 1.0

                        return ExchangeRates(
                            rates=rates,
                            timestamp=datetime.now(),
                            source="frankfurter.app"
                        )
        except Exception as e:
            logger.debug(f"Frankfurter API failed: {e}")
        return None

    def convert(self, amount: float, from_currency: str, to_currency: str = "USD") -> float:
        """
        Convert an amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code (default: USD)

        Returns:
            Converted amount
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency == to_currency:
            return amount

        rates = self.rates

        # Get rate to USD for source currency
        from_rate = rates.get(from_currency)
        if from_rate is None:
            logger.warning(f"Unknown currency: {from_currency}, using 1:1")
            from_rate = 1.0

        # Convert to USD first
        usd_amount = amount * from_rate

        # If target is USD, we're done
        if to_currency == "USD":
            return usd_amount

        # Otherwise convert from USD to target
        to_rate = rates.get(to_currency)
        if to_rate is None:
            logger.warning(f"Unknown currency: {to_currency}, using 1:1")
            to_rate = 1.0

        return usd_amount / to_rate

    def to_usd(self, amount: float, from_currency: str) -> float:
        """Convenience method to convert to USD."""
        return self.convert(amount, from_currency, "USD")


# Global converter instance
_converter: Optional[CurrencyConverter] = None


def get_converter() -> CurrencyConverter:
    """Get or create the global converter instance."""
    global _converter
    if _converter is None:
        _converter = CurrencyConverter()
    return _converter


async def ensure_rates_loaded() -> CurrencyConverter:
    """Ensure exchange rates are loaded, fetching if needed."""
    converter = get_converter()
    await converter.update_rates()
    return converter


def parse_price(price_str: str) -> Tuple[float, str]:
    """
    Parse a price string into amount and currency.

    Handles formats like:
    - "$299" -> (299.0, "USD")
    - "US$299" -> (299.0, "USD")
    - "R$1.500" -> (1500.0, "BRL")
    - "R$ 1.500,00" -> (1500.0, "BRL")
    - "COP 1.200.000" -> (1200000.0, "COP")
    - "ARS 250.000" -> (250000.0, "ARS")
    - "€299" -> (299.0, "EUR")
    - "£299" -> (299.0, "GBP")

    Returns:
        Tuple of (amount, currency_code)
    """
    if not price_str:
        return (0.0, "USD")

    price_str = price_str.strip()

    # Currency symbol mapping
    symbol_to_currency = {
        "$": "USD",
        "US$": "USD",
        "R$": "BRL",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
        "₱": "PHP",
        "₹": "INR",
    }

    # Check for currency prefix
    currency = "USD"  # Default

    # Check for explicit currency codes
    currency_match = re.match(r'^(USD|BRL|COP|ARS|EUR|GBP|MXN|CLP|PEN)\s*', price_str, re.IGNORECASE)
    if currency_match:
        currency = currency_match.group(1).upper()
        price_str = price_str[currency_match.end():]

    # Check for currency symbols
    for symbol, curr in symbol_to_currency.items():
        if price_str.startswith(symbol):
            currency = curr
            price_str = price_str[len(symbol):].strip()
            break

    # Handle Brazilian/European format (1.234,56) vs US format (1,234.56)
    # If has comma followed by exactly 2 digits at end, it's decimal separator
    if re.search(r',\d{2}$', price_str):
        # Brazilian/European format: 1.234,56
        price_str = price_str.replace('.', '').replace(',', '.')
    else:
        # US format or no decimals: 1,234.56 or 1,234
        price_str = price_str.replace(',', '')

    # Extract numeric value
    numeric_match = re.search(r'[\d.]+', price_str)
    if numeric_match:
        try:
            amount = float(numeric_match.group())
            return (amount, currency)
        except ValueError:
            pass

    return (0.0, "USD")


def normalize_price(price_str: str, expected_currency: str = None) -> float:
    """
    Parse a price string and convert to USD.

    Args:
        price_str: Price string like "$299" or "R$1.500"
        expected_currency: Override detected currency (useful when you know the POS)

    Returns:
        Price in USD
    """
    amount, detected_currency = parse_price(price_str)

    # Use expected currency if provided and different from detected
    currency = expected_currency or detected_currency

    converter = get_converter()
    return converter.to_usd(amount, currency)


async def normalize_price_async(price_str: str, expected_currency: str = None) -> float:
    """Async version that ensures rates are loaded first."""
    await ensure_rates_loaded()
    return normalize_price(price_str, expected_currency)
