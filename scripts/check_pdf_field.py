"""Проверка PDF поля в Bitrix."""
import asyncio
from app.services.http_client import bx

async def main():
    item = (await bx('crm.item.get', {
        'entityTypeId': 1050,
        'id': 491,
        'select': ['id', '*', 'ufCrm%']
    })).get('item')
    
    pdf_field = item.get('ufCrm7UfCrmPdfFile')
    print(f'PDF field: {pdf_field}')
    print(f'Type: {type(pdf_field)}')
    print(f'All keys with pdf: {[k for k in item.keys() if "pdf" in k.lower() or "lpa" in k.lower()]}')

if __name__ == "__main__":
    asyncio.run(main())



