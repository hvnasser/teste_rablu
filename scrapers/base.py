"""
Base classes shared by all site scrapers.

Every new site wrapper must:
1. Inherit from BaseScraper
2. Set class attributes: site_key, display_name, base_url
3. Implement search_products()
4. Register itself in scrapers/__init__.py

Nothing else needs to change.
"""

from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Page

from config import SCRAPER

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Product:
    """Canonical product representation returned by every scraper."""

    name: str
    brand: str                          # normalised brand key (e.g. "zimmermann")
    category: str                       # e.g. "dresses"
    site: str                           # site key (e.g. "farfetch")
    product_url: str
    price: float
    currency: str = "USD"
    original_price: Optional[float] = None   # pre-discount price, if shown
    discount_percent: Optional[float] = None
    image_url: Optional[str] = None
    sku: Optional[str] = None           # site-internal product id, if extractable

    def __post_init__(self) -> None:
        # Auto-compute discount when both prices are available
        if (
            self.discount_percent is None
            and self.original_price
            and self.original_price > self.price
        ):
            self.discount_percent = round(
                (self.original_price - self.price) / self.original_price * 100, 1
            )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "site": self.site,
            "product_url": self.product_url,
            "price": self.price,
            "currency": self.currency,
            "original_price": self.original_price,
            "discount_percent": self.discount_percent,
            "image_url": self.image_url,
            "sku": self.sku,
        }


# ---------------------------------------------------------------------------
# Base scraper
# ---------------------------------------------------------------------------

class BaseScraper(ABC):
    """
    Abstract base for all site scrapers.

    Subclasses receive an already-opened Playwright Page and must implement
    `search_products`. Helper methods handle delays, safe text extraction, and
    price parsing so wrappers stay concise.
    """

    # --- Override in every subclass ---
    site_key: str = ""          # matches the key in config.SITES
    display_name: str = ""
    base_url: str = ""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.logger = logging.getLogger(f"scraper.{self.site_key}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def search_products(self, brand: str, category: str) -> list[Product]:
        """
        Return all products matching *brand* and *category* available on this site.

        Parameters
        ----------
        brand:    normalised brand key from config.BRANDS  (e.g. "zimmermann")
        category: category string from config.CATEGORIES   (e.g. "dresses")
        """

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    async def _goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate and wait; retries once on timeout."""
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=SCRAPER["timeout_ms"])
        except Exception as exc:
            self.logger.warning("First navigation attempt failed (%s), retrying…", exc)
            await asyncio.sleep(3)
            await self.page.goto(url, wait_until=wait_until, timeout=SCRAPER["timeout_ms"])

    async def _random_delay(self) -> None:
        delay = random.uniform(SCRAPER["min_delay_s"], SCRAPER["max_delay_s"])
        await asyncio.sleep(delay)

    async def _text(self, selector: str, default: str = "") -> str:
        """Return stripped inner text of the first matching element."""
        try:
            el = await self.page.query_selector(selector)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            pass
        return default

    async def _attr(self, selector: str, attr: str, default: str = "") -> str:
        """Return an attribute value of the first matching element."""
        try:
            el = await self.page.query_selector(selector)
            if el:
                val = await el.get_attribute(attr)
                return (val or "").strip()
        except Exception:
            pass
        return default

    @staticmethod
    def _parse_price(raw: str) -> Optional[float]:
        """
        Parse a price string like '$1,250.00' or '1.250,00' into a float.
        Returns None if parsing fails.
        """
        if not raw:
            return None
        cleaned = ""
        for ch in raw:
            if ch.isdigit() or ch in ".,-":
                cleaned += ch
        # Handle European format: 1.250,00  → 1250.00
        if "," in cleaned and "." in cleaned:
            if cleaned.index(",") > cleaned.index("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned and cleaned.rfind(",") == len(cleaned) - 3:
            # single comma used as decimal separator
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _detect_currency(raw: str) -> str:
        symbols = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY", "A$": "AUD"}
        for sym, code in symbols.items():
            if sym in raw:
                return code
        # ISO codes
        for code in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD"):
            if code in raw.upper():
                return code
        return "USD"
