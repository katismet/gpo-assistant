import asyncio
from app.services.http_client import bx

async def main():
    item = (await bx('crm.item.get', {'entityTypeId': 1050, 'id': 491, 'select': ['id', '*', 'ufCrm%']})).get('item')
    print('UF_PDF_FILE:', item.get('ufCrm7UfCrmPdfFile'))

asyncio.run(main())
