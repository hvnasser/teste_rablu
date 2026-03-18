"""
Scraper Inspector — ferramenta de diagnóstico de seletores.

Acessa cada site configurado, tenta encontrar cards de produto e imprime
o HTML real + quais seletores funcionam. Use para calibrar os scrapers.

Uso:
    python inspect_selectors.py                        # todos os sites
    python inspect_selectors.py --site farfetch        # site específico
    python inspect_selectors.py --site farfetch --save # salva HTML completo
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Sites e URLs de teste (ajuste conforme necessário)
# ---------------------------------------------------------------------------
TEST_URLS: dict[str, str] = {
    "farfetch":     "https://www.farfetch.com/br/shopping/women/zimmermann/items.aspx?category=135979",
    "mytheresa":    "https://www.mytheresa.com/en-us/women/clothing/dresses?prefn1=brand&prefv1=Zimmermann",
    "netaporter":   "https://www.net-a-porter.com/en-us/shop/designer/zimmermann?pageSize=48&priceBand=sale",
    "ssense":       "https://www.ssense.com/en-us/women/zimmermann?catId=dress",
    "theoutnet":    "https://www.theoutnet.com/en-us/shop/designer/zimmermann?category=dresses",
    "zimmermann":   "https://www.zimmermann.com/en-us/collections/dresses",
    "maje":         "https://us.maje.com/en/c/dresses-skirts/dresses",
    "isabelmarant": "https://www.isabelmarant.com/en-us/women/clothing/dresses",
}

# Candidatos a seletores de card — do mais específico ao mais genérico
CARD_CANDIDATES: list[str] = [
    # data-testid (padrão React)
    "[data-testid='productCard']",
    "[data-testid='product-card']",
    "[data-testid='ProductCard']",
    "[data-testid='product_card']",
    # aria / role
    "[role='listitem']",
    # classes comuns
    ".product-card",
    ".product-tile",
    ".product__item",
    ".product-item",
    ".ProductCard",
    ".ProductTile",
    "[class*='productCard']",
    "[class*='ProductCard']",
    "[class*='product-card']",
    "[class*='product_card']",
    "[class*='ProductItem']",
    "[class*='product-item']",
    "[class*='tile']",
    # genérico — grid de produtos
    "li[class]",
]

# Candidatos a seletores de preço
PRICE_CANDIDATES: list[str] = [
    # data-testid
    "[data-testid='price']",
    "[data-testid='price-current-price']",
    "[data-testid='current-price']",
    "[data-testid='sale-price']",
    # classes
    "[class*='price']",
    "[class*='Price']",
    ".sales .value",
    ".price--sale",
    ".price-sale",
    ".final-price",
    ".current-price",
    ".sale-price",
    "span[itemprop='price']",
    "[data-price]",
]

# Candidatos a seletores de nome
NAME_CANDIDATES: list[str] = [
    "[data-testid='productDescription']",
    "[data-testid='product-name']",
    "[data-testid='product-title']",
    "[class*='productName']",
    "[class*='product-name']",
    "[class*='product-title']",
    "[class*='ProductName']",
    ".product-tile__name",
    ".product-tile__title",
    ".product__name",
    ".product-name",
    "h2[class]",
    "h3[class]",
]


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------

async def inspect_site(
    site: str,
    url: str,
    save_html: bool = False,
) -> dict:
    report: dict = {"site": site, "url": url, "card_selector": None, "count": 0, "sample": None, "prices": [], "names": []}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()

        print(f"\n{'='*60}")
        print(f"  Inspecionando: {site.upper()}")
        print(f"  URL: {url}")
        print(f"{'='*60}")

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        except Exception as e:
            print(f"  [AVISO] goto: {e}")

        # Aguarda lazy-loading
        await asyncio.sleep(4)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(3)

        # Tenta aceitar cookies automaticamente
        for cookie_sel in [
            "[data-testid='cookie-accept-all']", "#onetrust-accept-btn-handler",
            ".cookie-accept", "[class*='cookie'] button", "button[id*='accept']",
        ]:
            try:
                el = await page.query_selector(cookie_sel)
                if el and await el.is_visible():
                    await el.click()
                    print(f"  Cookie aceito via: {cookie_sel}")
                    await asyncio.sleep(2)
                    break
            except Exception:
                pass

        full_html = await page.content()

        if save_html:
            path = Path(f"/tmp/{site}_full.html")
            path.write_text(full_html, encoding="utf-8")
            print(f"  HTML completo salvo em: {path}")

        # ---- Encontra seletor de card ----
        best_selector = None
        best_count = 0

        for sel in CARD_CANDIDATES:
            try:
                elements = await page.query_selector_all(sel)
                n = len(elements)
                if n > 0:
                    print(f"  [card] {sel!r:60s} → {n} elementos")
                    if n > best_count:
                        best_count = n
                        best_selector = sel
            except Exception:
                pass

        report["card_selector"] = best_selector
        report["count"] = best_count

        if not best_selector:
            print("  ✗ Nenhum seletor de card funcionou.")
            # Dump body classes para análise
            body_html = await page.evaluate("document.body.innerHTML")
            classes = set(re.findall(r'class="([^"]+)"', body_html[:50000]))
            print("  Classes encontradas (amostra):")
            for c in sorted(classes)[:30]:
                print(f"    {c}")
        else:
            print(f"\n  ✓ Melhor seletor de card: {best_selector!r} ({best_count} resultados)")

            # HTML do primeiro card
            cards = await page.query_selector_all(best_selector)
            if cards:
                sample_html = await cards[0].inner_html()
                report["sample"] = sample_html[:2000]
                print(f"\n  --- HTML do primeiro card (primeiros 1500 chars) ---")
                print(f"  {sample_html[:1500]}")

                # ---- Preços dentro do card ----
                print("\n  --- Seletores de preço (dentro do card) ---")
                for sel in PRICE_CANDIDATES:
                    try:
                        el = await cards[0].query_selector(sel)
                        if el:
                            text = (await el.inner_text()).strip()
                            attr = await el.get_attribute("class") or ""
                            print(f"  [preço] {sel!r:50s} → {text!r}  (class={attr!r})")
                            report["prices"].append({"selector": sel, "value": text})
                    except Exception:
                        pass

                # ---- Nomes dentro do card ----
                print("\n  --- Seletores de nome (dentro do card) ---")
                for sel in NAME_CANDIDATES:
                    try:
                        el = await cards[0].query_selector(sel)
                        if el:
                            text = (await el.inner_text()).strip()
                            attr = await el.get_attribute("class") or ""
                            print(f"  [nome] {sel!r:50s} → {text!r}  (class={attr!r})")
                            report["names"].append({"selector": sel, "value": text})
                    except Exception:
                        pass

                # ---- Links ----
                print("\n  --- Links encontrados no card ---")
                links = await cards[0].query_selector_all("a[href]")
                for lnk in links[:5]:
                    href = await lnk.get_attribute("href") or ""
                    txt = (await lnk.inner_text()).strip()[:80]
                    print(f"  [link] {href!r} → {txt!r}")

                # ---- Imagens ----
                print("\n  --- Imagens encontradas no card ---")
                imgs = await cards[0].query_selector_all("img")
                for img in imgs[:3]:
                    src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
                    alt = await img.get_attribute("alt") or ""
                    print(f"  [img] src={src[:80]!r}  alt={alt!r}")

        await browser.close()

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def main(sites: list[str], save_html: bool) -> None:
    reports = []
    for site in sites:
        url = TEST_URLS.get(site)
        if not url:
            print(f"Site desconhecido: {site}. Disponíveis: {list(TEST_URLS.keys())}")
            continue
        r = await inspect_site(site, url, save_html=save_html)
        reports.append(r)

    # Resumo final
    print(f"\n{'='*60}")
    print("  RESUMO")
    print(f"{'='*60}")
    for r in reports:
        status = f"✓ {r['count']} cards ({r['card_selector']})" if r["card_selector"] else "✗ nenhum card encontrado"
        print(f"  {r['site']:15s} {status}")

    # Salva JSON com todos os resultados
    Path("/tmp/inspect_report.json").write_text(
        json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("\n  Relatório completo salvo em /tmp/inspect_report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspeciona seletores dos scrapers")
    parser.add_argument("--site", nargs="+", default=list(TEST_URLS.keys()),
                        help="Site(s) a inspecionar")
    parser.add_argument("--save", action="store_true",
                        help="Salva o HTML completo de cada página em /tmp/")
    args = parser.parse_args()

    asyncio.run(main(args.site, args.save))
