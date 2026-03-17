"""Isabel Marant official site scraper wrapper."""

from __future__ import annotations

import logging

from config import SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

_CATEGORY_URLS: dict[str, str] = {
    "dresses": "/en-us/women/clothing/dresses",
    "skirts": "/en-us/women/clothing/skirts",
}


class IsabelMarantScraper(BaseScraper):
    site_key = "isabelmarant"
    display_name = "Isabel Marant Official"
    base_url = "https://www.isabelmarant.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        cat_path = _CATEGORY_URLS.get(category, "/en-us/women/clothing")
        url = f"{self.base_url}{cat_path}?prefn1=isOnSale&prefv1=true"

        self.logger.info("GET %s", url)
        await self._goto(url)
        await self._random_delay()

        try:
            btn = await self.page.query_selector("#onetrust-accept-btn-handler, .cookie-accept")
            if btn:
                await btn.click()
                await self._random_delay()
        except Exception:
            pass

        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await self._random_delay()

        products: list[Product] = []
        cards = await self.page.query_selector_all(".product-tile, [class*='ProductCard']")

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
        name_el = await card.query_selector(".product-tile__name, [class*='productName']")
        name_text = (await name_el.inner_text()).strip() if name_el else ""
        if not name_text:
            return None

        link_el = await card.query_selector("a[href]")
        href = (await link_el.get_attribute("href") or "") if link_el else ""
        product_url = href if href.startswith("http") else self.base_url + href

        price_el = await card.query_selector(".sales .value, [class*='salePrice'], [class*='priceValue']")
        orig_el = await card.query_selector(".strike-through .value, [class*='originalPrice']")

        price_raw = (await price_el.inner_text()).strip() if price_el else ""
        orig_raw = (await orig_el.inner_text()).strip() if orig_el else ""

        price = self._parse_price(price_raw)
        if price is None:
            return None

        currency = self._detect_currency(price_raw)
        original_price = self._parse_price(orig_raw) if orig_raw else None

        img_el = await card.query_selector("img")
        image_url = ""
        if img_el:
            image_url = (
                await img_el.get_attribute("src")
                or await img_el.get_attribute("data-src")
                or ""
            )

        return Product(
            name=name_text,
            brand=brand,
            category=category,
            site=self.site_key,
            product_url=product_url,
            price=price,
            currency=currency,
            original_price=original_price,
            image_url=image_url,
        )
