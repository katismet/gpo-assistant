"""Отладка загрузки enum для ресурсов."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID

async def main():
    # Получаем ресурсы со смены 491
    res = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType', 'ufCrm9UfEquipType'],
        'limit': 10
    })
    
    items = res.get('items', [])
    print(f"Найдено ресурсов: {len(items)}")
    
    for item in items[:5]:
        res_id = item.get('id')
        enum_value = item.get('ufCrm9UfResourceType')
        mat_type = item.get('ufCrm9UfMatType')
        equip_type = item.get('ufCrm9UfEquipType')
        
        print(f"\nРесурс {res_id}:")
        print(f"  UF_RESOURCE_TYPE: {enum_value} (type: {type(enum_value)})")
        print(f"  mat_type: {mat_type}")
        print(f"  equip_type: {equip_type}")
        
        # Определяем тип по контексту
        if equip_type and not mat_type:
            print(f"  -> Определен как: Техника")
        elif mat_type:
            print(f"  -> Определен как: Материал")

if __name__ == "__main__":
    asyncio.run(main())



