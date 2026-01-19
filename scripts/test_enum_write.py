"""Тест записи enum значения в Bitrix."""
import asyncio
from app.services.http_client import bx
from app.services.bitrix_ids import RESOURCE_ETID
from app.bitrix_field_map import resolve_code, upper_to_camel
from app.services.resource_meta import resource_type_bitrix_label
from app.services.bitrix_enums import enum_payload

async def main():
    # Получаем существующий ресурс для теста
    res_list = await bx('crm.item.list', {
        'entityTypeId': RESOURCE_ETID,
        'filter': {'ufCrm9UfShiftId': 491},
        'select': ['id', 'ufCrm9UfResourceType'],
        'limit': 1
    })
    
    if not res_list.get('items'):
        print("Нет ресурсов для теста")
        return
    
    test_res_id = res_list['items'][0]['id']
    print(f"Тестируем ресурс ID: {test_res_id}")
    print(f"Текущее значение UF_RESOURCE_TYPE: {res_list['items'][0].get('ufCrm9UfResourceType')}")
    
    # Пробуем разные форматы записи
    f_res_type = resolve_code("Ресурс", "UF_RESOURCE_TYPE")
    f_res_type_camel = upper_to_camel(f_res_type) if f_res_type and f_res_type.startswith("UF_") else None
    
    print(f"\nПоле: {f_res_type} -> {f_res_type_camel}")
    
    # Вариант 1: {"value": "Материал"}
    label = resource_type_bitrix_label("MAT")
    payload1 = enum_payload(label)
    print(f"\nВариант 1: {payload1}")
    
    # Пробуем обновить
    try:
        result1 = await bx('crm.item.update', {
            'entityTypeId': RESOURCE_ETID,
            'id': test_res_id,
            'fields': {f_res_type_camel: payload1}
        })
        print(f"Результат варианта 1: {result1.get('item', {}).get('id') if isinstance(result1, dict) else result1}")
        
        # Проверяем, что записалось
        check1 = await bx('crm.item.get', {
            'entityTypeId': RESOURCE_ETID,
            'id': test_res_id,
            'select': ['id', f_res_type_camel]
        })
        print(f"После записи варианта 1: {check1.get('item', {}).get(f_res_type_camel)}")
    except Exception as e:
        print(f"Ошибка варианта 1: {e}")

if __name__ == "__main__":
    asyncio.run(main())



