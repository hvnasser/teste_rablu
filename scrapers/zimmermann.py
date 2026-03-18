"""
Zimmermann official site scraper wrapper.

Em vez de parsear HTML com Playwright, usa a SearchSpring API que o site
já expõe publicamente para carregar os produtos.

Endpoint:
  https://kxmyk2.a.searchspring.io/api/search/search.json
  ?siteId=kxmyk2
  &bgfilter.ss_category_hierarchy={category}
  &resultsFormat=native
  &resultsPerPage=100
  &sort.price=asc

O siteId=kxmyk2 é específico do Zimmermann e foi capturado pelo inspector.
"""

from __future__ import annotations

import html
import logging

import httpx

from config import SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

_SEARCHSPRING_URL = "https://kxmyk2.a.searchspring.io/api/search/search.json"
_SITE_ID = "kxmyk2"

# Valores de ss_category_hierarchy usados pelo Zimmermann
# (confirme abrindo a rede no browser em zimmermann.com/en-ca/collections/dresses)
_CATEGORY_FILTER: dict[str, str] = {
    "dresses": "Clothing > Dresses",
    "skirts":  "Clothing > Skirts",
}

_HEADERS = {
    "User-Agent": SCRAPER["user_agent"],
    "Accept": "application/json",
    "Referer": "https://www.zimmermann.com/",
    "Origin":  "https://www.zimmermann.com",
}


class ZimmermannScraper(BaseScraper):
    site_key = "zimmermann"
    display_name = "Zimmermann Official"
    base_url = "https://www.zimmermann.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        cat_filter = _CATEGORY_FILTER.get(category, "Clothing")

        params = {
            "siteId": _SITE_ID,
            "bgfilter.ss_category_hierarchy": cat_filter,
            "resultsFormat": "native",
            "resultsPerPage": SCRAPER["max_products_per_brand_category"],
            "sort.price": "asc",
        }

        self.logger.info("SearchSpring API: category=%s", cat_filter)

        try:
            async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
                resp = await client.get(_SEARCHSPRING_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            self.logger.error("SearchSpring request failed: %s", exc)
            return []

        results = data.get("results", [])
        self.logger.info("SearchSpring returned %d results", len(results))

        products: list[Product] = []
        for item in results:
            try:
                product = self._parse_item(item, brand, category)
                if product:
                    products.append(product)
            except Exception as exc:
                self.logger.debug("Item parse error: %s", exc)

        return products

    def _parse_item(self, item: dict, brand: str, category: str):
        name = item.get("name") or item.get("title") or ""
        if not name:
            return None

        # URL do produto — campo "url" já é completo (https://...)
        product_url = item.get("url") or self.base_url

        # Preços — SearchSpring retorna strings; "msrp" = preço original
        price_raw = str(item.get("price") or "")
        orig_raw  = str(item.get("msrp") or "")

        price = self._parse_price(price_raw)
        if price is None:
            return None

        # en-ca store usa CAD
        currency = "CAD"
        original_price = self._parse_price(orig_raw) if orig_raw else None
        # Só reporta original_price se há desconto real
        if original_price and original_price <= price:
            original_price = None

        # Imagem — URLs têm &amp; que precisa ser descodificado
        raw_img = item.get("thumbnailImageUrl") or item.get("imageUrl") or ""
        image_url = html.unescape(raw_img)

        # SKU
        sku = str(item.get("sku") or item.get("uid") or "")

        return Product(
            name=name,
            brand=brand,
            category=category,
            site=self.site_key,
            product_url=product_url,
            price=price,
            currency=currency,
            original_price=original_price,
            image_url=image_url,
            sku=sku,
        )
