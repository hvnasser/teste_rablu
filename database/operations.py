"""
High-level database operations used by the orchestrator and dashboard.

All functions accept / return plain Python dicts or dataclasses to keep
the rest of the codebase decoupled from Supabase internals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from database.client import get_client
from scrapers.base import Product

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

def upsert_product(product: Product) -> int:
    """
    Insert or update a product row and return its database id.
    The unique key is (product_url, site).
    """
    client = get_client()

    data = {
        "site": product.site,
        "brand": product.brand,
        "category": product.category,
        "name": product.name,
        "product_url": product.product_url,
        "image_url": product.image_url,
        "sku": product.sku,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    response = (
        client.table("products")
        .upsert(data, on_conflict="product_url,site")
        .execute()
    )

    row = response.data[0]
    return row["id"]


def insert_price(product_id: int, product: Product) -> None:
    """Record a new price snapshot for *product_id*."""
    client = get_client()

    client.table("price_history").insert(
        {
            "product_id": product_id,
            "price": product.price,
            "currency": product.currency,
            "original_price": product.original_price,
            "discount_percent": product.discount_percent,
        }
    ).execute()


def save_product(product: Product) -> int:
    """Convenience: upsert product + insert price. Returns product id."""
    product_id = upsert_product(product)
    insert_price(product_id, product)
    return product_id


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_latest_prices(
    brand: Optional[str] = None,
    site: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """
    Return rows from the `latest_prices` view with optional filters.
    """
    client = get_client()
    q = client.table("latest_prices").select("*")

    if brand:
        q = q.eq("brand", brand)
    if site:
        q = q.eq("site", site)
    if category:
        q = q.eq("category", category)

    return q.order("discount_percent", desc=True).execute().data


def get_price_history(product_id: int) -> list[dict]:
    """Return all price snapshots for a product, oldest first."""
    client = get_client()
    return (
        client.table("price_history")
        .select("*")
        .eq("product_id", product_id)
        .order("scraped_at")
        .execute()
        .data
    )


def get_previous_price(product_id: int) -> Optional[float]:
    """Return the second-to-last recorded price for *product_id*, or None."""
    client = get_client()
    rows = (
        client.table("price_history")
        .select("price")
        .eq("product_id", product_id)
        .order("scraped_at", desc=True)
        .limit(2)
        .execute()
        .data
    )
    if len(rows) < 2:
        return None
    return rows[1]["price"]


def get_cross_site_prices(product_name: str, brand: str) -> list[dict]:
    """
    Return latest price rows for all sites that carry a product with a
    matching name + brand, for cross-site comparison.
    """
    client = get_client()
    return (
        client.table("latest_prices")
        .select("*")
        .eq("brand", brand)
        .ilike("name", f"%{product_name}%")
        .order("price")
        .execute()
        .data
    )


def log_alert(alert_type: str, product_id: Optional[int], message: str) -> None:
    """Persist an alert record in the price_alerts table."""
    client = get_client()
    client.table("price_alerts").insert(
        {
            "alert_type": alert_type,
            "product_id": product_id,
            "message": message,
        }
    ).execute()
