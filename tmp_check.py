import asyncio
import json
from app.services.http_client import bx

async def main():
    resp = await bx('crm.item.userfield.list', {'entityTypeId': 1050})
    print(json.dumps(resp, ensure_ascii=False, indent=2))

asyncio.run(main())
