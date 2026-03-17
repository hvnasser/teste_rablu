"""
Scraper registry.

Maps every site key (used in config.SITES) to its scraper class.

To add a new site:
  1. Create scrapers/<sitename>.py with a class that inherits BaseScraper.
  2. Add one line here: "sitename": SiteNameScraper
  That's it — no other file needs to change.
"""

from scrapers.farfetch import FarfetchScraper
from scrapers.mytheresa import MytheresaScraper
from scrapers.netaporter import NetaPorterScraper
from scrapers.ssense import SSENSEScraper
from scrapers.theoutnet import TheOutnetScraper
from scrapers.zimmermann import ZimmermannScraper
from scrapers.maje import MajeScraper
from scrapers.isabelmarant import IsabelMarantScraper
from scrapers.base import BaseScraper, Product  # re-export for convenience

# ---------------------------------------------------------------------------
# Registry: site_key → scraper class
# ---------------------------------------------------------------------------
REGISTRY: dict[str, type[BaseScraper]] = {
    "farfetch": FarfetchScraper,
    "mytheresa": MytheresaScraper,
    "netaporter": NetaPorterScraper,
    "ssense": SSENSEScraper,
    "theoutnet": TheOutnetScraper,
    "zimmermann": ZimmermannScraper,
    "maje": MajeScraper,
    "isabelmarant": IsabelMarantScraper,
}


def get_scraper_class(site_key: str) -> type[BaseScraper]:
    """Return the scraper class for *site_key*, or raise KeyError."""
    if site_key not in REGISTRY:
        raise KeyError(
            f"No scraper registered for site '{site_key}'. "
            f"Available: {list(REGISTRY.keys())}"
        )
    return REGISTRY[site_key]


__all__ = ["REGISTRY", "get_scraper_class", "BaseScraper", "Product"]
