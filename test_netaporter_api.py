"""
Investiga a API interna da Net-a-Porter.

NAP usa Next.js e Algolia para busca. Este script testa os endpoints
de API mais prováveis para listagem de produtos.

Uso:
    uv run python test_netaporter_api.py
"""
import asyncio
import json
import httpx

BASE = "https://www.net-a-porter.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.net-a-porter.com/",
}

# NAP usa Algolia para busca de produtos no frontend
# Também tem endpoints internos Next.js
ENDPOINTS = [
    # NAP API interna (padrões conhecidos)
    "/api/products/listing?designer=zimmermann&category=dresses&priceBand=sale&locale=en-us",
    "/en-us/shop/designer/zimmermann?pageSize=12&priceBand=sale&format=json",
    # Next.js data fetching
    "/_next/data/en-us/shop/designer/zimmermann.json?pageSize=12",
    # Algolia via proxy (alguns sites expõem)
    "/api/search/products?q=zimmermann+dresses",
    # Sitemap para descobrir produtos
    "/sitemap_products_1.xml",
    "/sitemap.xml",
]

async def probe(client: httpx.AsyncClient, path: str) -> None:
    url = BASE + path
    try:
        r = await client.get(url, follow_redirects=False)
        ct = r.headers.get("content-type", "")
        preview = r.text[:300].replace("\n", " ")
        loc = r.headers.get("location", "")
        print(f"[{r.status_code}] {path}")
        if loc:
            print(f"  → Redirect: {loc}")
        print(f"  Content-Type: {ct}")
        print(f"  Preview: {preview[:200]}")
        if r.status_code == 200 and "json" in ct:
            try:
                data = r.json()
                print(f"  JSON keys: {list(data.keys())[:10]}")
            except Exception:
                pass
    except Exception as e:
        print(f"[ERR] {path} → {e}")
    print()

async def main():
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        for ep in ENDPOINTS:
            await probe(client, ep)

asyncio.run(main())
