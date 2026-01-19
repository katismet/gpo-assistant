"""Тест _infer_label_from_item."""
import asyncio
from app.services.bitrix_enums import get_resource_type_enum
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID

async def main():
    # Получаем ресурсы
    res = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType', 'ufCrm9UfEquipType'],
        'limit': 5
    })
    
    items = res.get('items', [])
    resource_enum = get_resource_type_enum()
    
    print("Тест _infer_label_from_item:")
    for item in items[:5]:
        enum_id = item.get('ufCrm9UfResourceType')
        if enum_id and enum_id > 0:
            label = await resource_enum._infer_label_from_item(item, enum_id)
            print(f"  Ресурс {item.get('id')}: enum_id={enum_id}, label={label}")

if __name__ == "__main__":
    asyncio.run(main())



