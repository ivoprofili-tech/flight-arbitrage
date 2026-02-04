"""
Proxy Configuration for Geo Location Arbitrage

Supports multiple proxy providers with country-level targeting.
Configure via environment variables or direct configuration.

Supported Providers:
- BrightData (formerly Luminati)
- Oxylabs
- Smartproxy
- Custom SOCKS5/HTTP proxies

Environment Variables:
    PROXY_PROVIDER: Provider name (brightdata, oxylabs, smartproxy, custom)
    PROXY_USERNAME: Username/Zone ID
    PROXY_PASSWORD: Password
    PROXY_HOST: Host (for custom proxies)
    PROXY_PORT: Port (for custom proxies)
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class LocationConfig:
    """Configuration for a specific geographic location."""
    code: str           # ISO country code (BR, US, CO, etc.)
    name: str           # Human-readable name
    locale: str         # Browser locale (pt-BR, en-US, etc.)
    language: str       # Accept-Language header
    currency: str       # Expected currency code
    timezone: str       # Timezone for the location
    google_domain: str  # Google domain for that region


# Target locations for geo arbitrage
LOCATIONS: Dict[str, LocationConfig] = {
    "BR": LocationConfig(
        code="BR",
        name="Brazil",
        locale="pt-BR",
        language="pt-BR,pt;q=0.9,en;q=0.8",
        currency="BRL",
        timezone="America/Sao_Paulo",
        google_domain="google.com.br",
    ),
    "US": LocationConfig(
        code="US",
        name="United States",
        locale="en-US",
        language="en-US,en;q=0.9",
        currency="USD",
        timezone="America/New_York",
        google_domain="google.com",
    ),
    "CO": LocationConfig(
        code="CO",
        name="Colombia",
        locale="es-CO",
        language="es-CO,es;q=0.9,en;q=0.8",
        currency="COP",
        timezone="America/Bogota",
        google_domain="google.com.co",
    ),
    "PA": LocationConfig(
        code="PA",
        name="Panama",
        locale="es-PA",
        language="es-PA,es;q=0.9,en;q=0.8",
        currency="USD",  # Panama uses USD
        timezone="America/Panama",
        google_domain="google.com.pa",
    ),
    "AR": LocationConfig(
        code="AR",
        name="Argentina",
        locale="es-AR",
        language="es-AR,es;q=0.9,en;q=0.8",
        currency="ARS",
        timezone="America/Buenos_Aires",
        google_domain="google.com.ar",
    ),
}


@dataclass
class ProxyConfig:
    """
    Proxy configuration for a specific request.

    Can be passed directly to Playwright browser context.
    """
    server: str                    # Proxy server URL (http://host:port)
    username: Optional[str] = None
    password: Optional[str] = None
    country: Optional[str] = None  # Target country code

    def to_playwright_proxy(self) -> Dict[str, Any]:
        """Convert to Playwright proxy format."""
        proxy = {"server": self.server}
        if self.username:
            proxy["username"] = self.username
        if self.password:
            proxy["password"] = self.password
        return proxy

    def __str__(self) -> str:
        if self.country:
            return f"Proxy({self.country} via {self.server})"
        return f"Proxy({self.server})"


class ProxyProvider:
    """Base class for proxy providers."""

    def get_proxy(self, country_code: str) -> Optional[ProxyConfig]:
        """Get a proxy for the specified country."""
        raise NotImplementedError


class BrightDataProvider(ProxyProvider):
    """
    BrightData (Luminati) proxy provider.

    Format: http://username-country-{country}:password@host:port
    """

    def __init__(
        self,
        username: str,
        password: str,
        host: str = "brd.superproxy.io",
        port: int = 22225,
    ):
        self.username = username
        self.password = password
        self.host = host
        self.port = port

    def get_proxy(self, country_code: str) -> ProxyConfig:
        # BrightData uses country codes in the username
        user_with_country = f"{self.username}-country-{country_code.lower()}"
        server = f"http://{self.host}:{self.port}"

        return ProxyConfig(
            server=server,
            username=user_with_country,
            password=self.password,
            country=country_code,
        )


class OxylabsProvider(ProxyProvider):
    """
    Oxylabs proxy provider.

    Format: http://customer-{username}-cc-{country}:password@host:port
    """

    def __init__(
        self,
        username: str,
        password: str,
        host: str = "pr.oxylabs.io",
        port: int = 7777,
    ):
        self.username = username
        self.password = password
        self.host = host
        self.port = port

    def get_proxy(self, country_code: str) -> ProxyConfig:
        user_with_country = f"customer-{self.username}-cc-{country_code.lower()}"
        server = f"http://{self.host}:{self.port}"

        return ProxyConfig(
            server=server,
            username=user_with_country,
            password=self.password,
            country=country_code,
        )


class SmartproxyProvider(ProxyProvider):
    """
    Smartproxy provider.

    Format: http://user-{username}-country-{country}:password@host:port
    """

    def __init__(
        self,
        username: str,
        password: str,
        host: str = "gate.smartproxy.com",
        port: int = 7000,
    ):
        self.username = username
        self.password = password
        self.host = host
        self.port = port

    def get_proxy(self, country_code: str) -> ProxyConfig:
        user_with_country = f"user-{self.username}-country-{country_code.lower()}"
        server = f"http://{self.host}:{self.port}"

        return ProxyConfig(
            server=server,
            username=user_with_country,
            password=self.password,
            country=country_code,
        )


class CustomProxyProvider(ProxyProvider):
    """
    Custom proxy provider with per-country proxy URLs.

    Useful for self-hosted proxies or other providers.
    """

    def __init__(self, proxies: Dict[str, str]):
        """
        Args:
            proxies: Dict mapping country codes to proxy URLs
                     e.g., {"BR": "socks5://user:pass@brazil-proxy:1080"}
        """
        self.proxies = proxies

    def get_proxy(self, country_code: str) -> Optional[ProxyConfig]:
        proxy_url = self.proxies.get(country_code.upper())
        if not proxy_url:
            return None

        return ProxyConfig(
            server=proxy_url,
            country=country_code,
        )


# Global proxy provider instance
_proxy_provider: Optional[ProxyProvider] = None


def init_proxy_provider(
    provider: str = None,
    username: str = None,
    password: str = None,
    host: str = None,
    port: int = None,
    custom_proxies: Dict[str, str] = None,
) -> ProxyProvider:
    """
    Initialize the global proxy provider.

    Args:
        provider: Provider name (brightdata, oxylabs, smartproxy, custom)
        username: Provider username
        password: Provider password
        host: Custom host (optional)
        port: Custom port (optional)
        custom_proxies: Dict of country->proxy URL for custom provider

    Can also be configured via environment variables:
        PROXY_PROVIDER, PROXY_USERNAME, PROXY_PASSWORD, PROXY_HOST, PROXY_PORT
    """
    global _proxy_provider

    # Read from environment if not provided
    provider = provider or os.environ.get("PROXY_PROVIDER", "").lower()
    username = username or os.environ.get("PROXY_USERNAME", "")
    password = password or os.environ.get("PROXY_PASSWORD", "")
    host = host or os.environ.get("PROXY_HOST")
    port = port or int(os.environ.get("PROXY_PORT", "0")) or None

    if provider == "brightdata":
        kwargs = {"username": username, "password": password}
        if host:
            kwargs["host"] = host
        if port:
            kwargs["port"] = port
        _proxy_provider = BrightDataProvider(**kwargs)

    elif provider == "oxylabs":
        kwargs = {"username": username, "password": password}
        if host:
            kwargs["host"] = host
        if port:
            kwargs["port"] = port
        _proxy_provider = OxylabsProvider(**kwargs)

    elif provider == "smartproxy":
        kwargs = {"username": username, "password": password}
        if host:
            kwargs["host"] = host
        if port:
            kwargs["port"] = port
        _proxy_provider = SmartproxyProvider(**kwargs)

    elif provider == "custom" and custom_proxies:
        _proxy_provider = CustomProxyProvider(custom_proxies)

    else:
        logger.warning(f"No valid proxy provider configured (provider={provider})")
        _proxy_provider = None

    return _proxy_provider


def get_proxy_for_location(country_code: str) -> Optional[ProxyConfig]:
    """
    Get a proxy configuration for the specified country.

    Args:
        country_code: ISO country code (BR, US, CO, PA, AR)

    Returns:
        ProxyConfig if provider is configured, None otherwise
    """
    if _proxy_provider is None:
        return None

    return _proxy_provider.get_proxy(country_code.upper())


def get_location_config(country_code: str) -> Optional[LocationConfig]:
    """Get the location configuration for a country code."""
    return LOCATIONS.get(country_code.upper())


def list_available_locations() -> list[str]:
    """List all available location codes."""
    return list(LOCATIONS.keys())


# Try to auto-initialize from environment on import
if os.environ.get("PROXY_PROVIDER"):
    init_proxy_provider()
