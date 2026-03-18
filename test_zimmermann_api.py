"""
Teste direto da SearchSpring API do Zimmermann.
Mostra o JSON bruto de um produto para confirmar os campos corretos.

Uso:
    uv run python test_zimmermann_api.py
"""
import asyncio
import json
import httpx

URL = "https://kxmyk2.a.searchspring.io/api/search/search.json"
PARAMS = {
    "siteId": "kxmyk2",
    "bgfilter.ss_category_hierarchy": "Clothing > Dresses",
    "resultsFormat": "native",
    "resultsPerPage": "3",
    "sort.price": "asc",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.zimmermann.com/",
}

async def main():
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        resp = await client.get(URL, params=PARAMS)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        total = data.get("pagination", {}).get("totalResults", "?")
        results = data.get("results", [])
        print(f"Total results: {total}")
        print(f"Returned: {len(results)}\n")
        if results:
            print("=== Campos do primeiro produto ===")
            print(json.dumps(results[0], indent=2, ensure_ascii=False))

asyncio.run(main())
