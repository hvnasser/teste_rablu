"""
Investiga a API interna da Mytheresa.

O inspector capturou https://www.mytheresa.com/api com status 200.
Este script testa endpoints conhecidos de sites Next.js/nuxt de luxo.

Uso:
    uv run python test_mytheresa_api.py
"""
import asyncio
import json
import httpx

BASE = "https://www.mytheresa.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.mytheresa.com/",
    "x-requested-with": "XMLHttpRequest",
}

# Candidatos de endpoint — padrões comuns em sites de luxo com Vue/Nuxt/Next
ENDPOINTS = [
    # Padrão Mytheresa conhecido (Magento headless)
    "/api/catalog/v1/products?categories=women_designers_zimmermann_clothing_dresses&locale=en_us&pageSize=24",
    "/api/catalog/products?category=women-designers-zimmermann-clothing-dresses&page=1",
    "/api/v1/catalog/categories/women/designers/zimmermann/clothing/dresses",
    # Algolia (alguns sites de luxo usam)
    "/api/search?query=zimmermann+dresses&category=women",
    # Endpoint simples de introspection
    "/api",
    "/api/v1",
    "/api/catalog",
]

async def probe(client: httpx.AsyncClient, path: str) -> None:
    url = BASE + path
    try:
        r = await client.get(url, follow_redirects=True)
        ct = r.headers.get("content-type", "")
        preview = r.text[:300].replace("\n", " ")
        print(f"[{r.status_code}] {path}")
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
