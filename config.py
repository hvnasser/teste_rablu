"""
Fashion Price Monitor — central configuration file.

To add a new brand:  insert an entry in BRANDS.
To add a new site:   create scrapers/<sitename>.py, then insert an entry in SITES.
To add a category:   insert an entry in CATEGORIES.
No other Python file needs to change.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Brands to monitor
# ---------------------------------------------------------------------------
BRANDS: dict[str, dict] = {
    "zimmermann": {
        "display_name": "Zimmermann",
        "search_terms": ["zimmermann"],
        "official_site": "zimmermann",
        # Slugs usados em cada multi-brand retailer (URL path ou query param)
        "slugs": {
            "farfetch":   "zimmermann",
            "mytheresa":  "zimmermann",
            "netaporter": "zimmermann",
            "ssense":     "zimmermann",
            "theoutnet":  "zimmermann",
        },
    },
    "maje": {
        "display_name": "Maje",
        "search_terms": ["maje"],
        "official_site": "maje",
        "slugs": {
            "farfetch":   "maje",
            "mytheresa":  "maje",
            "netaporter": "maje",
            "ssense":     "maje",
            "theoutnet":  "maje",
        },
    },
    "isabel_marant": {
        "display_name": "Isabel Marant",
        "search_terms": ["isabel marant"],
        "official_site": "isabelmarant",
        "slugs": {
            "farfetch":   "isabel-marant",
            "mytheresa":  "isabel-marant",
            "netaporter": "isabel-marant",
            "ssense":     "isabel-marant",
            "theoutnet":  "isabel-marant",
        },
    },
}

# ---------------------------------------------------------------------------
# Product categories to scrape
# ---------------------------------------------------------------------------
CATEGORIES: list[str] = ["dresses", "skirts"]

# ---------------------------------------------------------------------------
# Sites to scrape
# key        – unique identifier used throughout the code
# scraper    – module name inside scrapers/ (without .py)
# brands     – which brands to look for on this site (None = all)
# enabled    – easy on/off toggle without deleting config
# ---------------------------------------------------------------------------
SITES: dict[str, dict] = {
    # --- Multi-brand retailers ---
    "farfetch": {
        "display_name": "Farfetch",
        "base_url": "https://www.farfetch.com",
        "scraper": "farfetch",
        "brands": None,          # monitor all configured brands
        "enabled": True,
    },
    "mytheresa": {
        "display_name": "Mytheresa",
        "base_url": "https://www.mytheresa.com",
        "scraper": "mytheresa",
        "brands": None,
        "enabled": True,
    },
    "netaporter": {
        "display_name": "Net-a-Porter",
        "base_url": "https://www.net-a-porter.com",
        "scraper": "netaporter",
        "brands": None,
        "enabled": True,
    },
    "ssense": {
        "display_name": "SSENSE",
        "base_url": "https://www.ssense.com",
        "scraper": "ssense",
        "brands": None,
        "enabled": True,
    },
    "theoutnet": {
        "display_name": "The Outnet",
        "base_url": "https://www.theoutnet.com",
        "scraper": "theoutnet",
        "brands": None,
        "enabled": True,
    },
    # --- Official brand sites ---
    "zimmermann": {
        "display_name": "Zimmermann Official",
        "base_url": "https://www.zimmermann.com",
        "scraper": "zimmermann",
        "brands": ["zimmermann"],
        "enabled": True,
    },
    "maje": {
        "display_name": "Maje Official",
        "base_url": "https://us.maje.com",
        "scraper": "maje",
        "brands": ["maje"],
        "enabled": True,
    },
    "isabelmarant": {
        "display_name": "Isabel Marant Official",
        "base_url": "https://www.isabelmarant.com",
        "scraper": "isabelmarant",
        "brands": ["isabel_marant"],
        "enabled": True,
    },
}

# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------
ALERTS = {
    # Notify when price drops by at least this fraction compared to last recorded price
    "price_drop_threshold": 0.20,       # 20 %
    # Notify when a site is cheaper than the others by at least this fraction
    "cross_site_discount_threshold": 0.15,  # 15 %
}

# ---------------------------------------------------------------------------
# Scraping behaviour
# ---------------------------------------------------------------------------
SCRAPER = {
    "headless": True,
    "timeout_ms": 30_000,
    "max_products_per_brand_category": 50,
    # Randomised delay range between requests (seconds)
    "min_delay_s": 2,
    "max_delay_s": 6,
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ---------------------------------------------------------------------------
# Supabase
# (values are read from environment variables; see .env.example)
# ---------------------------------------------------------------------------
import os

SUPABASE = {
    "url": os.getenv("SUPABASE_URL", ""),
    "key": os.getenv("SUPABASE_KEY", ""),
}

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
TELEGRAM = {
    "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
}
