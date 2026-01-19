"""Проверка реальных значений enum полей в Bitrix."""
import asyncio
import json
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID, SHIFT_ETID

async def main():
    # Проверяем реальный ресурс с заполненным типом
    print("=== Проверка ресурса с типом ===")
    res_list = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType', 'ufCrm9UfEquipType'],
        'limit': 3
    })
    
    for item in res_list.get('items', [])[:3]:
        print(f"\nResource ID: {item.get('id')}")
        print(f"  UF_RESOURCE_TYPE raw: {item.get('ufCrm9UfResourceType')}")
        print(f"  Type: {type(item.get('ufCrm9UfResourceType'))}")
        print(f"  Material: {item.get('ufCrm9UfMatType')}")
        print(f"  Equipment: {item.get('ufCrm9UfEquipType')}")
        if isinstance(item.get('ufCrm9UfResourceType'), dict):
            print(f"  Dict keys: {list(item.get('ufCrm9UfResourceType', {}).keys())}")
    
    # Проверяем реальную смену с типом и статусом
    print("\n=== Проверка смены с типом и статусом ===")
    shift = await bx('crm.item.get', {
        'entityTypeId': SHIFT_ETID,
        'id': 491,
        'select': ['id', 'ufCrm7UfCrmShiftType', 'ufCrm7UfCrmStatus', 'statusId']
    })
    
    shift_item = shift.get('item', shift)
    print(f"Shift ID: {shift_item.get('id')}")
    print(f"  UF_SHIFT_TYPE raw: {shift_item.get('ufCrm7UfCrmShiftType')}")
    print(f"  Type: {type(shift_item.get('ufCrm7UfCrmShiftType'))}")
    print(f"  UF_STATUS raw: {shift_item.get('ufCrm7UfCrmStatus')}")
    print(f"  Type: {type(shift_item.get('ufCrm7UfCrmStatus'))}")
    print(f"  statusId: {shift_item.get('statusId')}")
    
    if isinstance(shift_item.get('ufCrm7UfCrmShiftType'), dict):
        print(f"  Shift type dict keys: {list(shift_item.get('ufCrm7UfCrmShiftType', {}).keys())}")
    if isinstance(shift_item.get('ufCrm7UfCrmStatus'), dict):
        print(f"  Status dict keys: {list(shift_item.get('ufCrm7UfCrmStatus', {}).keys())}")

if __name__ == "__main__":
    asyncio.run(main())



