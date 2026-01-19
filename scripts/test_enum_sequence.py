"""Тест последовательного создания ресурсов с разными типами."""
import asyncio
from app.services.resource_client import bitrix_add_resource
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID

async def main():
    # Создаем ресурс с типом MAT
    print("1. Создаем ресурс с типом MAT...")
    res1_data = {
        "shift_id": 491,
        "resource_type": "MAT",
        "mat_type": "Песок тест",
        "mat_qty": 1,
        "mat_unit": "т",
        "mat_price": 100,
    }
    result1 = await bitrix_add_resource(res1_data)
    res1_id = result1.get("result", {}).get("item", {}).get("id") if isinstance(result1, dict) else None
    print(f"   Ресурс создан: ID={res1_id}")
    
    if res1_id:
        check1 = await bx('crm.item.get', {
            'entityTypeId': RESOURCE_ETID,
            'id': res1_id,
            'select': ['id', 'ufCrm9UfResourceType']
        })
        print(f"   UF_RESOURCE_TYPE: {check1.get('item', {}).get('ufCrm9UfResourceType')}")
    
    # Ждем немного
    await asyncio.sleep(1)
    
    # Создаем ресурс с типом EQUIP
    print("\n2. Создаем ресурс с типом EQUIP...")
    res2_data = {
        "shift_id": 491,
        "resource_type": "EQUIP",
        "equip_type": "Экскаватор тест",
        "equip_hours": 8,
        "equip_rate": 2000,
    }
    result2 = await bitrix_add_resource(res2_data)
    res2_id = result2.get("result", {}).get("item", {}).get("id") if isinstance(result2, dict) else None
    print(f"   Ресурс создан: ID={res2_id}")
    
    if res2_id:
        check2 = await bx('crm.item.get', {
            'entityTypeId': RESOURCE_ETID,
            'id': res2_id,
            'select': ['id', 'ufCrm9UfResourceType']
        })
        print(f"   UF_RESOURCE_TYPE: {check2.get('item', {}).get('ufCrm9UfResourceType')}")
    
    print(f"\nСравнение: MAT={check1.get('item', {}).get('ufCrm9UfResourceType')}, EQUIP={check2.get('item', {}).get('ufCrm9UfResourceType')}")

if __name__ == "__main__":
    asyncio.run(main())



