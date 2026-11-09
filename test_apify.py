import asyncio, json
from curl_cffi.requests import AsyncSession

async def main():
    TOKEN = "ВСТАВЬ_APIFY_TOKEN"
    url = f"https://api.apify.com/v2/acts/aurenic~kufar-scraper/run-sync-get-dataset-items?token={TOKEN}"
    body = {"searchQueries": ["BMW X5"], "maxItems": 5}
    async with AsyncSession(impersonate="chrome124", timeout=60) as s:
        r = await s.post(url, json=body)
        print(f"HTTP {r.status_code}")
        try:
            data = r.json()
            print(f"items: {len(data)}")
            for item in data[:3]:
                print(f"  {item.get('title')} | {item.get('priceByn')} BYN | {item.get('url')}")
        except Exception:
            print(r.text[:500])

asyncio.run(main())