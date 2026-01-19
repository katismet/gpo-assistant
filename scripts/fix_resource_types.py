"""Исправление типов ресурсов в Bitrix."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.resource_meta import resource_type_bitrix_label
from app.services.bitrix_enums import enum_payload

async def main():
    # Получаем все ресурсы смены 491
    res_list = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType', 'ufCrm9UfMatType', 'ufCrm9UfEquipType'],
    })
    
    f_res_type = resolve_code("Ресурс", "UF_RESOURCE_TYPE")
    f_res_type_camel = upper_to_camel(f_res_type) if f_res_type and f_res_type.startswith("UF_") else None
    
    print(f"Найдено ресурсов: {len(res_list.get('items', []))}")
    print(f"Поле: {f_res_type} -> {f_res_type_camel}\n")
    
    updated_count = 0
    for item in res_list.get('items', []):
        res_id = item['id']
        mat_type = item.get('ufCrm9UfMatType')
        equip_type = item.get('ufCrm9UfEquipType')
        current_type = item.get('ufCrm9UfResourceType')
        
        # Определяем тип ресурса
        if equip_type and not mat_type:
            resource_type = "EQUIP"
            label = resource_type_bitrix_label("EQUIP")
        elif mat_type:
            resource_type = "MAT"
            label = resource_type_bitrix_label("MAT")
        else:
            print(f"  Ресурс {res_id}: неопределенный тип (пропускаем)")
            continue
        
        # Обновляем тип ресурса
        payload = enum_payload(label)
        print(f"  Ресурс {res_id}: {resource_type} -> {label} ({payload})")
        
        try:
            result = await bx('crm.item.update', {
                'entityTypeId': RESOURCE_ETID,
                'id': res_id,
                'fields': {f_res_type_camel: payload}
            })
            
            # Проверяем результат
            check = await bx('crm.item.get', {
                'entityTypeId': RESOURCE_ETID,
                'id': res_id,
                'select': ['id', f_res_type_camel]
            })
            new_type = check.get('item', {}).get(f_res_type_camel)
            print(f"    Обновлено: {current_type} -> {new_type}")
            updated_count += 1
        except Exception as e:
            print(f"    Ошибка: {e}")
    
    print(f"\nОбновлено ресурсов: {updated_count}")

if __name__ == "__main__":
    asyncio.run(main())



