import os, asyncio, httpx, json
BASE, TOK = os.getenv("BITRIX_BASE"), os.getenv("BITRIX_TOKEN_PATH")
async def main():
    async with httpx.AsyncClient(timeout=30) as x:
        r = await x.get(f"{BASE}/rest/{TOK}/crm.item.list.json",
                        params={"entityTypeId":1,"select[]":["id","title"],"start":0})
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
asyncio.run(main())
