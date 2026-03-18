"""
Maje official site scraper wrapper.

URL: /en/c/dresses-skirts/{category}
"""

from __future__ import annotations

import logging

from config import SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

_CATEGORY_PATHS: dict[str, str] = {
    "dresses": "dresses",
    "skirts":  "skirts",
}

_CARD_CANDIDATES = [
    ".product-tile",
    "[class*='product-tile']",
    "[class*='ProductCard']",
    "[class*='product-card']",
    "li[class*='product']",
    "article[class*='product']",
]

_NAME_SELECTORS = [
    ".product-tile__name",
    ".tile-body .pdp-link a",
    "[class*='productName']",
    "[class*='product-name']",
    "[class*='tile-title']",
    "h3[class]",
    "h2[class]",
]

_PRICE_SELECTORS = [
    ".sales .value",
    ".price-sale .value",
    "[class*='price-sales']",
    "[class*='salePrice']",
    "[class*='currentPrice']",
    "span[class*='sales']",
    "span[class*='price']:not([class*='strike']):not([class*='original'])",
]

_ORIG_PRICE_SELECTORS = [
    ".strike-through .value",
    "[class*='strike-through']",
    "[class*='originalPrice']",
    "[class*='price-strike']",
    "del",
    "s[class]",
]

_COOKIE_SELECTORS = [
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
    "[class*='cookie-accept']",
]


class MajeScraper(BaseScraper):
    site_key = "maje"
    display_name = "Maje Official"
    base_url = "https://us.maje.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        cat = _CATEGORY_PATHS.get(category, "dresses")
        url = f"{self.base_url}/en/c/dresses-skirts/{cat}?start=0&sz=60"

        self.logger.info("GET %s", url)
        await self._goto(url, wait_until="domcontentloaded")
        await self._random_delay()

        for sel in _COOKIE_SELECTORS:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await self._random_delay()
                    break
            except Exception:
                pass

        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
        await self._random_delay()

        _sel, cards = await self._find_cards(_CARD_CANDIDATES)

        products: list[Product] = []
        for card in cards[: SCRAPER["max_products_per_brand_category"]]:
            try:
                product = await self._parse_card(card, brand, category)
                if product:
                    products.append(product)
            except Exception as exc:
                self.logger.debug("Card parse error: %s", exc)

        self.logger.info("Found %d products for %s / %s", len(products), brand, category)
        return products

    async def _parse_card(self, card, brand: str, category: str):
        name_text = await self._first_text(card, _NAME_SELECTORS)
        if not name_text:
            return None

        href = await self._first_attr(card, ["a[href]"], "href")
        product_url = href if href.startswith("http") else self.base_url + href

        price_raw = await self._first_text(card, _PRICE_SELECTORS)
        orig_raw = await self._first_text(card, _ORIG_PRICE_SELECTORS)

        price = self._parse_price(price_raw)
        if price is None:
            return None

        currency = self._detect_currency(price_raw)
        original_price = self._parse_price(orig_raw) if orig_raw else None

        img_url = await self._first_attr(card, ["img"], "src") or \
                  await self._first_attr(card, ["img"], "data-src")

        return Product(
            name=name_text,
            brand=brand,
            category=category,
            site=self.site_key,
            product_url=product_url,
            price=price,
            currency=currency,
            original_price=original_price,
            image_url=img_url,
        )
