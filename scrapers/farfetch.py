"""
Farfetch scraper wrapper.

URL real (fornecida pelo usuário):
  https://www.farfetch.com/br/shopping/women/zimmermann/items.aspx?category=135979

Estrutura:
  /{locale}/shopping/women/{brand_slug}/items.aspx?category={category_id}

IDs de categoria (Farfetch):
  dresses : 135979
  skirts  : 136301

Notas de implementação:
  - O Farfetch usa Emotion CSS — classes são geradas (ex: ltr-mhoyab) e mudam.
  - Atributos estáveis: data-testid e data-component.
  - O elemento <a data-component='ProductCardLink'> contém todo o texto do card
    no formato:  BRAND \n\n Name \n\n Price \n\n Installment \n\n ...
    Isso serve como fallback robusto quando seletores internos falham.
"""

from __future__ import annotations

import logging
import re

from config import BRANDS, SCRAPER
from scrapers.base import BaseScraper, Product

logger = logging.getLogger(__name__)

_LOCALE = "br"

_CATEGORY_IDS: dict[str, str] = {
    "dresses": "135979",
    "skirts":  "136301",
}

_CARD_CANDIDATES = [
    "[data-testid='productCard']",
    "[data-component='ProductCard']",
    "li[data-testid='productCard']",
    "[class*='ProductCard']",
]

# Seletores internos usando data-component (estáveis no Farfetch)
_NAME_SELECTORS = [
    "[data-component='ProductCardDescription']",
    "[data-testid='productDescription']",
    "[data-testid='productName']",
    "[data-component='ProductCardInfo'] p",
    "[data-component='ProductCardBrand'] + *",   # elemento após a marca
]

_PRICE_SELECTORS = [
    "[data-component='Price']",
    "[data-component='ProductCardPrice']",
    "[data-testid='price']",
    "[data-testid='price-current-price']",
    "[data-component='ProductCardInfo'] [class*='price']",
]

_ORIG_PRICE_SELECTORS = [
    "[data-component='PriceOriginal']",
    "[data-testid='price-original-price']",
    "[data-testid='price-was']",
]

_COOKIE_SELECTORS = [
    "[data-testid='cookie-accept-all']",
    "#onetrust-accept-btn-handler",
    "button[id*='accept']",
    "[class*='cookie'] button",
]


def _parse_link_text(text: str) -> tuple[str, str]:
    """
    Extrai (nome, preço_raw) do texto completo do ProductCardLink.

    Formato esperado (separado por \\n\\n):
      BRAND NAME
      Product Name
      R$ 12.751
      12 x R$ 1.062,58
      [desconto opcional]
    """
    parts = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    # parts[0] = marca (maiúsculo), parts[1] = nome, parts[2] = preço
    name = parts[1] if len(parts) > 1 else parts[0] if parts else ""
    price_raw = ""
    for part in parts[2:]:
        # pega a primeira parte que parece um preço (contém dígito e símbolo)
        if re.search(r"[\d]", part) and any(c in part for c in "$€£R"):
            price_raw = part
            break
    return name, price_raw


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

        for sel in _COOKIE_SELECTORS:
            try:
                btn = await self.page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await self._random_delay()
                    break
            except Exception:
                pass

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
        # --- Link e URL ---
        link_el = await card.query_selector("a[data-component='ProductCardLink'], a[href]")
        href = (await link_el.get_attribute("href") or "") if link_el else ""
        product_url = href if href.startswith("http") else self.base_url + href

        # --- Nome: tenta seletores específicos, depois parseia texto do link ---
        name_text = await self._first_text(card, _NAME_SELECTORS)
        price_raw = await self._first_text(card, _PRICE_SELECTORS)

        if not name_text or not price_raw:
            # Fallback: extrai do texto completo do link
            link_text = (await link_el.inner_text()).strip() if link_el else ""
            if link_text:
                fallback_name, fallback_price = _parse_link_text(link_text)
                if not name_text:
                    name_text = fallback_name
                if not price_raw:
                    price_raw = fallback_price

        if not name_text:
            return None

        # --- Preço original (se em promoção) ---
        orig_raw = await self._first_text(card, _ORIG_PRICE_SELECTORS)

        price = self._parse_price(price_raw)
        if price is None:
            return None

        currency = self._detect_currency(price_raw)
        original_price = self._parse_price(orig_raw) if orig_raw else None

        # --- Imagem ---
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
