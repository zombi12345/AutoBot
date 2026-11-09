import asyncio, os
from app.services.parsers.kufar import search

async def main():
    print("=== Kufar via ReefAPI: BMW X5 ===")
    res = await search({"brand": "BMW", "model": "X5"}, limit=10)
    print(f"results: {len(res)}")
    for r in res[:5]:
        print(f"  {r.get('price')} {r.get('currency')} | {r.get('year')} | {r['title'][:50]}")
        print(f"    {r.get('params')[:100]}")

asyncio.run(main())