"""Проверка enum ID для ресурсов."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID

async def main():
    res = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType', 'ufCrm9UfEquipType'],
        'limit': 30
    })
    
    items = res.get('items', [])
    mat_ids = set()
    equip_ids = set()
    
    for i in items:
        enum_id = i.get('ufCrm9UfResourceType')
        mat_type = i.get('ufCrm9UfMatType')
        equip_type = i.get('ufCrm9UfEquipType')
        
        if mat_type and not equip_type:
            mat_ids.add(enum_id)
        elif equip_type and not mat_type:
            equip_ids.add(enum_id)
    
    print(f"Материалы (enum_id): {sorted(mat_ids)}")
    print(f"Техника (enum_id): {sorted(equip_ids)}")
    print(f"\nВсего материалов: {len([i for i in items if i.get('ufCrm9UfMatType') and not i.get('ufCrm9UfEquipType')])}")
    print(f"Всего техники: {len([i for i in items if i.get('ufCrm9UfEquipType') and not i.get('ufCrm9UfMatType')])}")

if __name__ == "__main__":
    asyncio.run(main())



