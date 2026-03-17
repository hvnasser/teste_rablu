# Fashion Price Monitor

Automated daily tracker for luxury women's clothing prices across major e-commerces and official brand sites.

## Features

- **Scrapers**: Farfetch, Mytheresa, Net-a-Porter, SSENSE, The Outnet + official sites for Zimmermann, Maje and Isabel Marant
- **Categories**: Dresses and skirts (configurable)
- **Storage**: Supabase (PostgreSQL) — full price history per product
- **Alerts**: Telegram notifications for price drops ≥20% and cross-site deals
- **Dashboard**: Streamlit app with charts, filters and CSV export
- **Extensible**: Adding a new site requires only one new file + one line in the registry

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Configure credentials
cp .env.example .env
# edit .env with your Supabase and Telegram credentials

# 3. Create Supabase tables
# Paste the contents of database/schema.sql into the Supabase SQL editor

# 4. Run a scraping pass
python main.py

# 5. Start the dashboard
streamlit run dashboard/app.py
```

## Scheduled runs

```bash
# Run every day at 08:00
python main.py --schedule 08:00

# Scrape only specific sites or brands
python main.py --sites farfetch mytheresa --brands zimmermann maje
```

## Project structure

```
fashion_price_monitor/
├── config.py                  ← All configuration (brands, sites, thresholds)
├── main.py                    ← Orchestrator + CLI
├── scrapers/
│   ├── base.py                ← BaseScraper + Product dataclass
│   ├── __init__.py            ← Scraper registry (REGISTRY dict)
│   ├── farfetch.py
│   ├── mytheresa.py
│   ├── netaporter.py
│   ├── ssense.py
│   ├── theoutnet.py
│   ├── zimmermann.py
│   ├── maje.py
│   └── isabelmarant.py
├── database/
│   ├── client.py              ← Supabase client singleton
│   ├── operations.py          ← DB read/write helpers
│   └── schema.sql             ← Tables DDL (run once in Supabase)
├── notifications/
│   └── telegram.py            ← Alert functions
├── dashboard/
│   └── app.py                 ← Streamlit dashboard
├── requirements.txt
└── .env.example
```

## Adding a new site

1. Create `scrapers/mysite.py`:

```python
from scrapers.base import BaseScraper, Product

class MySiteScraper(BaseScraper):
    site_key = "mysite"
    display_name = "My Site"
    base_url = "https://www.mysite.com"

    async def search_products(self, brand: str, category: str) -> list[Product]:
        # ... your scraping logic ...
        return products
```

2. Register it in `scrapers/__init__.py`:

```python
from scrapers.mysite import MySiteScraper

REGISTRY = {
    ...
    "mysite": MySiteScraper,
}
```

3. Add a site entry in `config.py`:

```python
SITES = {
    ...
    "mysite": {
        "display_name": "My Site",
        "base_url": "https://www.mysite.com",
        "scraper": "mysite",
        "brands": None,   # None = all brands
        "enabled": True,
    },
}
```

That's it — no other file changes needed.

## Environment variables

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon or service-role key |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Chat/channel ID to receive alerts |
