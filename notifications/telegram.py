"""
Telegram alert sender.

Uses the Telegram Bot API (sendMessage) via httpx (async) so it runs
inside the same async loop as Playwright without blocking.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import ALERTS, TELEGRAM
from database.operations import log_alert
from scrapers.base import Product

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def _send(text: str) -> None:
    """Low-level: POST a message to the configured Telegram chat."""
    token = TELEGRAM["bot_token"]
    chat_id = TELEGRAM["chat_id"]

    if not token or not chat_id:
        logger.warning("Telegram not configured — skipping notification.")
        return

    url = _TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Telegram message sent (chat_id=%s)", chat_id)
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)


# ---------------------------------------------------------------------------
# Public alert functions
# ---------------------------------------------------------------------------

async def alert_price_drop(
    product: Product,
    product_id: int,
    previous_price: float,
) -> None:
    """
    Send an alert when a product's price has dropped by ≥ threshold.
    """
    drop_pct = (previous_price - product.price) / previous_price * 100

    if drop_pct < ALERTS["price_drop_threshold"] * 100:
        return

    message = (
        f"🔻 <b>Price Drop Alert</b>\n\n"
        f"<b>{product.name}</b>\n"
        f"Brand: {product.brand.replace('_', ' ').title()}\n"
        f"Site: {product.site}\n\n"
        f"Was: <s>{product.currency} {previous_price:,.2f}</s>\n"
        f"Now: <b>{product.currency} {product.price:,.2f}</b> "
        f"(↓ {drop_pct:.1f}%)\n\n"
        f"<a href='{product.product_url}'>View product →</a>"
    )

    await _send(message)
    log_alert("price_drop", product_id, message)
    logger.info("Price-drop alert sent for product_id=%d (%.1f%%)", product_id, drop_pct)


async def alert_cross_site_deal(
    cheapest: dict,
    others: list[dict],
    threshold_pct: Optional[float] = None,
) -> None:
    """
    Send an alert when one site is significantly cheaper than the others.

    Parameters
    ----------
    cheapest:      row from `latest_prices` view (cheapest site)
    others:        remaining rows for the same product (more expensive)
    threshold_pct: minimum % difference to trigger (defaults to config value)
    """
    threshold = threshold_pct or ALERTS["cross_site_discount_threshold"] * 100

    if not others:
        return

    avg_price = sum(r["price"] for r in others) / len(others)
    diff_pct = (avg_price - cheapest["price"]) / avg_price * 100

    if diff_pct < threshold:
        return

    other_lines = "\n".join(
        f"  • {r['site']}: {r['currency']} {r['price']:,.2f}" for r in others
    )
    message = (
        f"💰 <b>Best Price Deal Found</b>\n\n"
        f"<b>{cheapest['name']}</b>\n"
        f"Brand: {cheapest['brand'].replace('_', ' ').title()}\n\n"
        f"Cheapest on <b>{cheapest['site']}</b>: "
        f"{cheapest['currency']} {cheapest['price']:,.2f} "
        f"({diff_pct:.1f}% cheaper)\n\n"
        f"Other sites:\n{other_lines}\n\n"
        f"<a href='{cheapest['product_url']}'>Buy on {cheapest['site']} →</a>"
    )

    await _send(message)
    log_alert("cross_site_deal", cheapest.get("id"), message)
    logger.info(
        "Cross-site deal alert sent for '%s' (%.1f%% cheaper on %s)",
        cheapest["name"],
        diff_pct,
        cheapest["site"],
    )
