"""
Zimmermann official site scraper wrapper.

URL: /en-us/collections/{category}
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
    ".product-tile__title",
    ".product-tile__name",
    "[class*='productTitle']",
    "[class*='product-title']",
    "[class*='productName']",
    "h3[class]",
    "h2[class]",
    "p[class*='name']",
]

_PRICE_SELECTORS = [
    ".product-tile__price--sale",
    ".product-tile__price",
    "[class*='price--sale']",
    "[class*='salePrice']",
    "[class*='currentPrice']",
    "span[class*='price']:not([class*='original'])",
    "[data-price]",
]

_ORIG_PRICE_SELECTORS = [
    ".product-tile__price--original",
    ".product-tile__price--was",
    "[class*='price--original']",
    "[class*='originalPrice']",
    "s[class*='price']",
    "del",
]

_COOKIE_SELECTORS = [
    ".js-cookie-btn-accept",
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
    "[class*='cookie'] button",
]


class ZimmermannScraper(BaseScraper):
    site_key = "zimmermann"
    display_name = "Zimmermann Official"
    base_url = "https://www.zimmermann.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        cat = _CATEGORY_PATHS.get(category, "all")
        url = f"{self.base_url}/en-us/collections/{cat}?sort_by=price-ascending"

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
                  await self._first_attr(card, ["img"], "data-src") or \
                  await self._first_attr(card, ["img"], "data-srcset")

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
