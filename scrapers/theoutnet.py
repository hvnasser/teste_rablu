"""
The Outnet scraper wrapper.

URL:
  /en-us/shop/designer/{brand_slug}?category={category}
"""

from __future__ import annotations

import logging

from config import BRANDS, SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

_CATEGORY_SLUGS: dict[str, str] = {
    "dresses": "dresses",
    "skirts":  "skirts",
}

# The Outnet é do mesmo grupo da NAP — seletores similares
_CARD_CANDIDATES = [
    "[data-test='product-card']",
    "[data-testid='product-card']",
    "article[class*='product']",
    "[class*='ProductCard']",
    "[class*='product-card']",
    "li[class*='product']",
]

_NAME_SELECTORS = [
    "[data-test='product-description']",
    "[data-testid='product-description']",
    "[class*='productDescription']",
    "[class*='product-description']",
    "[class*='productName']",
    "h3[class]",
    "h2[class]",
]

_PRICE_SELECTORS = [
    "[data-test='current-price']",
    "[data-testid='current-price']",
    "[class*='currentPrice']",
    "[class*='salePrice']",
    "span[class*='price']:not(del):not(s)",
]

_ORIG_PRICE_SELECTORS = [
    "[data-test='full-price']",
    "[data-testid='full-price']",
    "[class*='fullPrice']",
    "[class*='originalPrice']",
    "del[class*='price']",
    "s[class*='price']",
]

_DISCOUNT_SELECTORS = [
    "[data-test='percentage-off']",
    "[data-testid='percentage-off']",
    "[class*='percentageOff']",
    "[class*='discount']",
]

_COOKIE_SELECTORS = [
    "[data-test='consent-accept']",
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
]


class TheOutnetScraper(BaseScraper):
    site_key = "theoutnet"
    display_name = "The Outnet"
    base_url = "https://www.theoutnet.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        brand_cfg = BRANDS[brand]
        brand_slug = brand_cfg["slugs"].get(self.site_key, brand_cfg["search_terms"][0])
        cat = _CATEGORY_SLUGS.get(category, "clothing")

        url = (
            f"{self.base_url}/en-us/shop/designer/{brand_slug}"
            f"?category={cat}&sortBy=percentageOff"
        )
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
        discount_raw = await self._first_text(card, _DISCOUNT_SELECTORS)

        price = self._parse_price(price_raw)
        if price is None:
            return None

        currency = self._detect_currency(price_raw)
        original_price = self._parse_price(orig_raw) if orig_raw else None

        discount_percent: float | None = None
        if discount_raw:
            dp = self._parse_price(discount_raw.replace("%", ""))
            discount_percent = abs(dp) if dp else None

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
            discount_percent=discount_percent,
            image_url=img_url,
        )
