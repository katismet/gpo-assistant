"""Проверка enum полей смены."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import SHIFT_ETID

async def main():
    shift = await bx('crm.item.get', {
        'entityTypeId': SHIFT_ETID,
        'id': 491,
        'select': ['id', 'ufCrm7UfCrmShiftType', 'ufCrm7UfCrmStatus', 'ufCrm7UfPlanJson']
    })
    
    item = shift.get('item', shift)
    print(f"UF_SHIFT_TYPE: {item.get('ufCrm7UfCrmShiftType')} (type: {type(item.get('ufCrm7UfCrmShiftType'))})")
    print(f"UF_STATUS: {item.get('ufCrm7UfCrmStatus')} (type: {type(item.get('ufCrm7UfCrmStatus'))})")
    
    # Проверяем plan_json
    plan_json_raw = item.get('ufCrm7UfPlanJson')
    if plan_json_raw:
        import json
        try:
            if isinstance(plan_json_raw, str):
                plan_json = json.loads(plan_json_raw)
            else:
                plan_json = plan_json_raw
            meta = plan_json.get('meta', {})
            print(f"plan_json.meta.shift_type: {meta.get('shift_type')}")
        except Exception as e:
            print(f"Ошибка парсинга plan_json: {e}")

if __name__ == "__main__":
    asyncio.run(main())

