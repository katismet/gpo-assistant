"""Проверка структуры enum полей в Bitrix."""
import asyncio
import json
from app.services.http_client import bx

async def main():
    # Проверяем структуру поля UF_RESOURCE_TYPE
    print("=== Проверка UF_RESOURCE_TYPE (Ресурс) ===")
    fields_resp = await bx('crm.item.fields', {'entityTypeId': 9})
    if 'fields' in fields_resp:
        res_type_field = fields_resp['fields'].get('ufCrm9UfResourceType') or fields_resp['fields'].get('UF_CRM_9_UF_RESOURCE_TYPE')
        if res_type_field:
            print(f"Field found: {json.dumps(res_type_field, indent=2, ensure_ascii=False)}")
        else:
            print("Field not found in fields response")
            print(f"Available fields: {list(fields_resp['fields'].keys())[:20]}")
    
    print("\n=== Проверка UF_SHIFT_TYPE (Смена) ===")
    fields_shift = await bx('crm.item.fields', {'entityTypeId': 1050})
    if 'fields' in fields_shift:
        shift_type_field = fields_shift['fields'].get('ufCrm7UfCrmShiftType') or fields_shift['fields'].get('UF_CRM_7_UF_CRM_SHIFT_TYPE')
        if shift_type_field:
            print(f"Field found: {json.dumps(shift_type_field, indent=2, ensure_ascii=False)}")
        else:
            print("Field not found")
            # Ищем все поля с shift
            shift_fields = {k: v for k, v in fields_shift['fields'].items() if 'shift' in k.lower() or 'type' in k.lower()}
            print(f"Fields with 'shift' or 'type': {list(shift_fields.keys())[:10]}")
    
    print("\n=== Проверка UF_STATUS (Смена) ===")
    if 'fields' in fields_shift:
        status_field = fields_shift['fields'].get('ufCrm7UfCrmStatus') or fields_shift['fields'].get('UF_CRM_7_UF_CRM_STATUS')
        if status_field:
            print(f"Field found: {json.dumps(status_field, indent=2, ensure_ascii=False)}")
        else:
            print("Field not found")
            # Ищем все поля со status
            status_fields = {k: v for k, v in fields_shift['fields'].items() if 'status' in k.lower()}
            print(f"Fields with 'status': {list(status_fields.keys())[:10]}")

if __name__ == "__main__":
    asyncio.run(main())



