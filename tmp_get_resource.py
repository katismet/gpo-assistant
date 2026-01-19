# -*- coding: utf-8 -*-
import asyncio, json
from app.services.http_client import bx

async def main():
    resp = await bx('crm.item.list', {
        'entityTypeId': 1056,
        'order': {'id': 'desc'},
        'limit': 1,
        'select': ['id', '*', 'ufCrm%']
    })
    print(json.dumps(resp, ensure_ascii=False, indent=2))

asyncio.run(main())
