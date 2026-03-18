"""
Farfetch scraper wrapper.

URL real (fornecida pelo usuário):
  https://www.farfetch.com/br/shopping/women/zimmermann/items.aspx?category=135979

Estrutura:
  /{locale}/shopping/women/{brand_slug}/items.aspx?category={category_id}

IDs de categoria (Farfetch) — confirme via inspect_selectors.py se mudarem:
  dresses : 135979
  skirts  : 136301
"""

from __future__ import annotations

import logging

from config import BRANDS, SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

# Locale da Farfetch a usar (br = BRL, en-us = USD)
_LOCALE = "br"

# Mapeamento categoria → ID de categoria Farfetch
_CATEGORY_IDS: dict[str, str] = {
    "dresses": "135979",
    "skirts":  "136301",
}

# Candidatos de seletor de card — testados em ordem
_CARD_CANDIDATES = [
    "[data-testid='productCard']",
    "li[data-testid='productCard']",
    "[data-component='ProductCard']",
    "[class*='ProductCard']",
    "[class*='product-card']",
    "li[class*='product']",
]

_NAME_SELECTORS = [
    "[data-testid='productDescription']",
    "[data-testid='productName']",
    "[data-testid='productDesigner']",
    "p[data-testid]",
    "[class*='productDescription']",
    "[class*='productName']",
    "h3",
    "h2",
]

_PRICE_SELECTORS = [
    "[data-testid='price-current-price']",
    "[data-testid='price']",
    "[class*='price_current']",
    "[class*='priceAmount']",
    "[class*='price-value']",
    "[class*='Price'] span",
    "span[class*='price']",
]

_ORIG_PRICE_SELECTORS = [
    "[data-testid='price-original-price']",
    "[data-testid='price-was']",
    "[class*='price_original']",
    "[class*='priceStrike']",
    "[class*='price-strike']",
    "s[class*='price']",
    "del[class*='price']",
]

_COOKIE_SELECTORS = [
    "[data-testid='cookie-accept-all']",
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
    "[class*='cookie'] button",
]


class FarfetchScraper(BaseScraper):
    site_key = "farfetch"
    display_name = "Farfetch"
    base_url = "https://www.farfetch.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        brand_cfg = BRANDS[brand]
        brand_slug = brand_cfg["slugs"].get(self.site_key, brand_cfg["search_terms"][0])
        category_id = _CATEGORY_IDS.get(category, "135979")

        url = (
            f"{self.base_url}/{_LOCALE}/shopping/women"
            f"/{brand_slug}/items.aspx?category={category_id}"
        )
        self.logger.info("GET %s", url)
        await self._goto(url, wait_until="domcontentloaded")
        await self._random_delay()

        # Aceita cookies
        for sel in _COOKIE_SELECTORS:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await self._random_delay()
                    break
            except Exception:
                pass

        # Scroll para ativar lazy-loading
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.4)")
        await self._random_delay()
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
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

        img_url = await self._first_attr(card, ["img"], "src")
        if not img_url:
            img_url = await self._first_attr(card, ["img"], "data-src")

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
