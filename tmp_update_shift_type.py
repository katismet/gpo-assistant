# -*- coding: utf-8 -*-
import asyncio
from app.services.http_client import bx

SHIFT_ID = 491

async def main():
    print('Updating shift', SHIFT_ID)
    upd = await bx('crm.item.update', {
        'entityTypeId': 1050,
        'id': SHIFT_ID,
        'fields': {
            'ufCrm7UfCrmShiftType': {'value': 'Дневная'}
        }
    })
    print('update resp:', upd)
    get_resp = await bx('crm.item.get', {'entityTypeId': 1050, 'id': SHIFT_ID})
    item = get_resp.get('item', get_resp)
    print('value after:', item.get('ufCrm7UfCrmShiftType'))

asyncio.run(main())
