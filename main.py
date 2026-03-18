"""
Fashion Price Monitor — main orchestrator.

Usage
-----
Run once immediately:
    python main.py

Run on a daily schedule (e.g. at 08:00):
    python main.py --schedule 08:00

Scrape only specific sites or brands:
    python main.py --sites farfetch mytheresa --brands zimmermann
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from playwright.async_api import async_playwright

from config import BRANDS, CATEGORIES, SCRAPER, SITES
from database.operations import (
    get_cross_site_prices,
    get_previous_price,
    save_product,
)
from notifications.telegram import alert_cross_site_deal, alert_price_drop
from scrapers import REGISTRY, get_scraper_class

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Core scraping logic
# ---------------------------------------------------------------------------

async def scrape_site(
    site_key: str,
    site_cfg: dict,
    brands_to_scrape: list[str],
    categories: list[str],
) -> list:
    """Open a Playwright page, run the scraper for every brand/category combo."""
    scraper_class = get_scraper_class(site_cfg["scraper"])
    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=SCRAPER["headless"])
        context = await browser.new_context(
            user_agent=SCRAPER["user_agent"],
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        page = await context.new_page()

        # Aplica stealth patches para reduzir detecção de bot
        try:
            from playwright_stealth import stealth_async
            await stealth_async(page)
        except ImportError:
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

        scraper = scraper_class(page)

        for brand in brands_to_scrape:
            for category in categories:
                logger.info(
                    "[%s] Scraping brand=%s category=%s …",
                    site_key, brand, category,
                )
                try:
                    products = await scraper.search_products(brand, category)
                    results.extend(products)
                    logger.info(
                        "[%s] ✓ %d products found for %s/%s",
                        site_key, len(products), brand, category,
                    )
                except Exception as exc:
                    logger.error(
                        "[%s] ✗ Error scraping %s/%s: %s",
                        site_key, brand, category, exc,
                    )

        await browser.close()

    return results


# ---------------------------------------------------------------------------
# Persist & alert
# ---------------------------------------------------------------------------

async def process_products(products: list) -> None:
    """Save each product to the database and trigger alerts when needed."""
    for product in products:
        try:
            # Retrieve previous price before inserting the new one
            from database.operations import get_previous_price, upsert_product
            product_id = upsert_product(product)
            previous_price = get_previous_price(product_id)

            # Save the new price snapshot
            from database.operations import insert_price
            insert_price(product_id, product)

            # --- Price-drop alert ---
            if previous_price is not None:
                await alert_price_drop(product, product_id, previous_price)

        except Exception as exc:
            logger.error("DB/alert error for '%s': %s", product.name, exc)

    # --- Cross-site comparison alerts ---
    # Group by (name, brand) and check if cheapest site is much cheaper
    seen: set[tuple] = set()
    for product in products:
        key = (product.name, product.brand)
        if key in seen:
            continue
        seen.add(key)

        try:
            rows = get_cross_site_prices(product.name, product.brand)
            if len(rows) >= 2:
                cheapest, *others = rows  # already sorted by price ASC
                await alert_cross_site_deal(cheapest, others)
        except Exception as exc:
            logger.error("Cross-site alert error for '%s': %s", product.name, exc)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run(
    site_keys: list[str] | None = None,
    brand_keys: list[str] | None = None,
) -> None:
    """Execute one full monitoring run."""
    start = datetime.now()
    logger.info("=== Fashion Price Monitor started at %s ===", start.isoformat())

    active_sites = {
        k: v for k, v in SITES.items()
        if v["enabled"] and (site_keys is None or k in site_keys)
    }
    active_brands = brand_keys or list(BRANDS.keys())

    all_products = []

    for site_key, site_cfg in active_sites.items():
        # Determine which brands to scrape on this site
        if site_cfg["brands"] is not None:
            brands = [b for b in active_brands if b in site_cfg["brands"]]
        else:
            brands = active_brands

        if not brands:
            logger.info("[%s] No matching brands — skipping.", site_key)
            continue

        products = await scrape_site(site_key, site_cfg, brands, CATEGORIES)
        all_products.extend(products)

    logger.info("Total products collected: %d", len(all_products))

    await process_products(all_products)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=== Run complete in %.1f s ===", elapsed)


# ---------------------------------------------------------------------------
# Scheduler (optional)
# ---------------------------------------------------------------------------

async def scheduled_run(time_str: str, **kwargs) -> None:
    """Block forever, running `run()` each day at *time_str* (HH:MM)."""
    import schedule
    import time as _time

    def _sync_run():
        asyncio.run(run(**kwargs))

    schedule.every().day.at(time_str).do(_sync_run)
    logger.info("Scheduled daily run at %s.", time_str)

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(description="Fashion Price Monitor")
    parser.add_argument(
        "--schedule",
        metavar="HH:MM",
        help="Run on a daily schedule at the given time (e.g. 08:00).",
    )
    parser.add_argument(
        "--sites",
        nargs="+",
        metavar="SITE",
        help=f"Limit to specific sites. Choices: {list(SITES.keys())}",
    )
    parser.add_argument(
        "--brands",
        nargs="+",
        metavar="BRAND",
        help=f"Limit to specific brands. Choices: {list(BRANDS.keys())}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    kwargs = {"site_keys": args.sites, "brand_keys": args.brands}

    if args.schedule:
        asyncio.run(scheduled_run(args.schedule, **kwargs))
    else:
        asyncio.run(run(**kwargs))
