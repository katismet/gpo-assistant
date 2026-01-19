# -*- coding: utf-8 -*-
import asyncio
from app.services.http_client import bx

SHIFT_ID = 491

async def main():
    print('Updating status for shift', SHIFT_ID)
    upd = await bx('crm.item.update', {
        'entityTypeId': 1050,
        'id': SHIFT_ID,
        'fields': {
            'ufCrm7UfCrmStatus': {'value': 'Закрыта'}
        }
    })
    print('update resp:', upd)
    item = (await bx('crm.item.get', {'entityTypeId': 1050, 'id': SHIFT_ID})).get('item')
    print('status after:', item.get('ufCrm7UfCrmStatus'))

asyncio.run(main())
