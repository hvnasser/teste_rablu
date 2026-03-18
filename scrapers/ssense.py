"""
SSENSE scraper wrapper.

URL:
  /en-us/women/{brand_slug}?catId={category_id}

IDs de categoria SSENSE:
  dresses: 10600 (ou usar slug 'clothing-dresses')
  skirts:  10500 (ou usar slug 'clothing-skirts')
"""

from __future__ import annotations

import logging

from config import BRANDS, SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

# catId por categoria (confirme via inspect_selectors.py)
_CATEGORY_IDS: dict[str, str] = {
    "dresses": "10600",
    "skirts":  "10500",
}

_CARD_CANDIDATES = [
    "[class*='ProductTile']",
    "[class*='product-tile']",
    "[class*='ProductCard']",
    "[data-testid='product-tile']",
    "article[class]",
    "li[class*='product']",
    "[class*='plpProduct']",
]

_NAME_SELECTORS = [
    "[class*='productName']",
    "[class*='ProductName']",
    "[class*='product-name']",
    "[class*='name']",
    "h3[class]",
    "h2[class]",
    "p[class*='name']",
]

_PRICE_SELECTORS = [
    "[class*='finalPrice']",
    "[class*='salePrice']",
    "[class*='reducedPrice']",
    "[class*='currentPrice']",
    "[class*='priceValue']",
    # fallback
    "span[class*='price']:not([class*='original']):not([class*='regular'])",
]

_ORIG_PRICE_SELECTORS = [
    "[class*='originalPrice']",
    "[class*='regularPrice']",
    "[class*='fullPrice']",
    "del[class*='price']",
    "s[class*='price']",
]

_COOKIE_SELECTORS = [
    ".onetrust-accept-btn-handler",
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
]


class SSENSEScraper(BaseScraper):
    site_key = "ssense"
    display_name = "SSENSE"
    base_url = "https://www.ssense.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        brand_cfg = BRANDS[brand]
        brand_slug = brand_cfg["slugs"].get(self.site_key, brand_cfg["search_terms"][0])
        cat_id = _CATEGORY_IDS.get(category, "10600")

        url = f"{self.base_url}/en-us/women/{brand_slug}?catId={cat_id}"
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
