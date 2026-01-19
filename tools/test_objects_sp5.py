import os
import asyncio
import httpx
import json

BASE = os.getenv("BITRIX_BASE")
TOK = os.getenv("BITRIX_TOKEN_PATH")

async def main():
    async with httpx.AsyncClient(timeout=20) as x:
        r = await x.get(f"{BASE}/rest/{TOK}/crm.item.list.json",
                        params={"entityTypeId": 5, "select[]": ["id", "title"], "start": 0})
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())