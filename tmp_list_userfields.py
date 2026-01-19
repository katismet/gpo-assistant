# -*- coding: utf-8 -*-
import asyncio
import json
from app.services.http_client import bx

async def main():
    resp = await bx('crm.userfield.list', {'filter': {'ENTITY_ID': 'CRM_1050'}})
    print(json.dumps(resp, ensure_ascii=False, indent=2))

asyncio.run(main())
